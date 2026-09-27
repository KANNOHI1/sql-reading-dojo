"""content/ の原稿を DuckDB で実行・検証し、lessons.js を生成する。

    python tools/build_lessons.py          # 検証して lessons.js を書く
    python tools/build_lessons.py --check  # lessons.js が原稿より古ければ失敗

途中経過の表（steps）は人が書かない。句ごとに「そこまでの累積クエリ」を
DuckDB で実行して得る。1 件でも検証に失敗したら lessons.js は書かない。
"""
from __future__ import annotations

import datetime as dt
import decimal
import hashlib
import json
import re
import sys
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
OUT = ROOT / "lessons.js"

# 実行順。句 → (順位, 表示名, アニメ種別, Alteryx ツール)
PHASES = {
    "FROM": (1, "表を取る", "appear", "入力データ"),
    "WHERE": (2, "行を絞る", "filter", "フィルター"),
    "SELECT": (3, "列を選ぶ", "project", "セレクト / フォーミュラ"),
    "DISTINCT": (4, "重複をまとめる", "collapse", "ユニーク"),
    "ORDER BY": (5, "並べる", "reorder", "ソート"),
    "LIMIT": (6, "先頭 N 行", "cut", "サンプル"),
}
SCORED = {"predict", "quiz"}


class BuildError(Exception):
    pass


def jsonable(v):
    if isinstance(v, bool) or v is None or isinstance(v, (int, float, str)):
        return v
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S UTC")
    if isinstance(v, dt.date):
        return v.isoformat()
    return str(v)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    con.execute((CONTENT / "datasets.sql").read_text(encoding="utf-8"))
    # 全行に _rid を付ける（アニメで行を追跡するための ID）
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='dojo'").fetchall()]
    for t in tables:
        con.execute(f"CREATE TABLE dojo.__tmp AS SELECT *, '{t}:' || row_number() OVER () AS _rid FROM dojo.{t}")
        con.execute(f"DROP TABLE dojo.{t}")
        con.execute(f"ALTER TABLE dojo.__tmp RENAME TO {t}")
    return con


def bq_to_duck(sql: str) -> str:
    return sql.replace("`", "")


def run(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = [list(r) for r in cur.fetchall()]
    return cols, rows


def split_result(cols, rows):
    """_rid / _members 列を分離し、表示列と行だけにする。"""
    hidden = {"_rid", "_members"}
    keep = [i for i, c in enumerate(cols) if c not in hidden]
    rid_i = cols.index("_rid") if "_rid" in cols else None
    mem_i = cols.index("_members") if "_members" in cols else None
    out_rows, rids, members = [], [], []
    for r in rows:
        out_rows.append([jsonable(r[i]) for i in keep])
        rids.append(r[rid_i] if rid_i is not None else None)
        members.append(list(r[mem_i]) if mem_i is not None else None)
    return [cols[i] for i in keep], out_rows, rids, members


def clause_text(lines, clause):
    parts = [l["sql"].strip() for l in lines if l["clause"] == clause]
    if not parts:
        return None
    text = " ".join(parts)
    # 先頭の句キーワードを剥がす
    return re.sub(rf"^{clause}\b\s*", "", text, flags=re.IGNORECASE).strip()


def line_ids(lines, clause):
    return [l["id"] for l in lines if l["clause"] == clause]


def build_steps(con, lesson_id, lines):
    """句のリストから実行順の steps を作る。S1 対応句: FROM WHERE SELECT (DISTINCT) ORDER BY LIMIT"""
    for l in lines:
        if l["clause"] not in PHASES or l["clause"] == "DISTINCT":
            raise BuildError(f"{lesson_id}: 未対応の句 {l['clause']!r}")
    frm = clause_text(lines, "FROM")
    sel = clause_text(lines, "SELECT")
    whr = clause_text(lines, "WHERE")
    odr = clause_text(lines, "ORDER BY")
    lim = clause_text(lines, "LIMIT")
    if not frm or not sel:
        raise BuildError(f"{lesson_id}: FROM と SELECT は必須")
    distinct = bool(re.match(r"^DISTINCT\b", sel, re.IGNORECASE))
    if distinct:
        sel = re.sub(r"^DISTINCT\b\s*", "", sel, flags=re.IGNORECASE)
    frm = bq_to_duck(frm)
    where_sql = f" WHERE {whr}" if whr else ""

    steps = []

    def add(phase, sql, lines_, cols, rows, rids, members=None):
        order, label, anim, tool = PHASES[phase]
        steps.append({
            "phase": phase, "label": label, "anim": anim, "tool": tool,
            "lines": lines_, "cols": cols, "rows": rows, "rid": rids,
            **({"members": members} if members else {}),
        })

    # FROM
    cols, rows, rids, _ = split_result(*run(con, f"SELECT * FROM {frm}"))
    add("FROM", None, line_ids(lines, "FROM"), cols, rows, rids)

    # WHERE
    if whr:
        cols, rows, rids, _ = split_result(*run(con, f"SELECT * FROM {frm}{where_sql}"))
        add("WHERE", None, line_ids(lines, "WHERE"), cols, rows, rids)

    # SELECT（射影。DISTINCT はまだ掛けない）
    proj_sql = f"SELECT {sel}, _rid FROM {frm}{where_sql}"
    cols, rows, rids, _ = split_result(*run(con, proj_sql))
    add("SELECT", None, line_ids(lines, "SELECT"), cols, rows, rids)

    tuple_to_rid = None
    if distinct:
        # 同じ値の行を束ね、束ねた元行の _rid を members に持つ
        dsql = f"SELECT {sel}, list(_rid) AS _members FROM {frm}{where_sql} GROUP BY ALL"
        cols, rows, _, members = split_result(*run(con, dsql))
        # 束ね行は元の表での初出順に並べる（GROUP BY ALL の出力順は不定）
        first_pos = {rid: i for i, rid in enumerate(steps[-1]["rid"])}
        order = sorted(range(len(rows)), key=lambda i: min(first_pos[m] for m in members[i]))
        rows = [rows[i] for i in order]; members = [members[i] for i in order]
        rids = [f"g:{i}" for i in range(len(rows))]
        tuple_to_rid = {json.dumps(r, ensure_ascii=False): rid for r, rid in zip(rows, rids)}
        add("DISTINCT", None, line_ids(lines, "SELECT"), cols, rows, rids, members)

    def rid_for(rows_, rids_):
        if tuple_to_rid is None:
            return rids_
        return [tuple_to_rid[json.dumps(r, ensure_ascii=False)] for r in rows_]

    head = f"SELECT DISTINCT {sel}" if distinct else f"SELECT {sel}, _rid"
    if odr:
        base = f"{head} FROM {frm}{where_sql} ORDER BY {odr}"
        cols, rows, rids, _ = split_result(*run(con, base))
        # 同順位で結果が揺れないか（_rid の昇順・降順で並びが変わらないこと）
        if not distinct:
            _, r_asc, _, _ = split_result(*run(con, base + ", _rid ASC"))
            _, r_desc, _, _ = split_result(*run(con, base + ", _rid DESC"))
            if r_asc != r_desc:
                raise BuildError(f"{lesson_id}: ORDER BY に同順位があり結果が一意に決まらない")
        add("ORDER BY", None, line_ids(lines, "ORDER BY"), cols, rows, rid_for(rows, rids))
    if lim:
        if not odr:
            raise BuildError(f"{lesson_id}: ORDER BY 無しの LIMIT は結果が不定。教材では使わない")
        sql = f"{head} FROM {frm}{where_sql} ORDER BY {odr} LIMIT {lim}"
        cols, rows, rids, _ = split_result(*run(con, sql))
        add("LIMIT", None, line_ids(lines, "LIMIT"), cols, rows, rid_for(rows, rids))

    # 検証 (a): 最終段階 = クエリ全体を素直に実行した結果（多重集合一致・ORDER BY があれば順序も）
    full_sql = bq_to_duck(" ".join(l["sql"].strip() for l in lines))
    fcols, frows, _, _ = split_result(*run(con, full_sql))
    last = steps[-1]
    if fcols != last["cols"]:
        raise BuildError(f"{lesson_id}: 列が一致しない {fcols} vs {last['cols']}")
    key = lambda r: json.dumps(r, ensure_ascii=False)
    if odr:
        if frows != last["rows"]:
            raise BuildError(f"{lesson_id}: 最終結果が全体実行と一致しない（順序）")
    elif sorted(map(key, frows)) != sorted(map(key, last["rows"])):
        raise BuildError(f"{lesson_id}: 最終結果が全体実行と一致しない")
    return steps


def check_task(lesson_id, task, steps):
    t = task["type"]
    final = steps[-1] if steps else None
    if t == "predict":
        ask = task["ask"]
        choices = task["choices"]
        ans = task["answer"]
        if ans not in choices:
            raise BuildError(f"{lesson_id}/{task['id']}: answer が choices に無い")
        if choices.count(ans) != 1:
            raise BuildError(f"{lesson_id}/{task['id']}: 正解が choices に複数ある")
        if ask == "rowCount":
            truth = len(final["rows"])
        elif ask == "colCount":
            truth = len(final["cols"])
        elif ask == "cell":
            has_order = any(s["phase"] == "ORDER BY" for s in steps)
            if not has_order and len(final["rows"]) > 1:
                raise BuildError(f"{lesson_id}/{task['id']}: cell は ORDER BY 付きか 1 行結果でのみ使える")
            if task["col"] not in final["cols"]:
                raise BuildError(f"{lesson_id}/{task['id']}: 列 {task['col']} が結果に無い {final['cols']}")
            truth = final["rows"][task["row"]][final["cols"].index(task["col"])]
        else:
            raise BuildError(f"{lesson_id}/{task['id']}: 未知の ask {ask}")
        if str(truth) != str(ans):
            raise BuildError(f"{lesson_id}/{task['id']}: answer={ans!r} だが実行結果は {truth!r}")
    elif t == "quiz":
        if not (0 <= task["answer"] < len(task["choices"])):
            raise BuildError(f"{lesson_id}/{task['id']}: quiz の answer が範囲外")
    elif t in ("vocab", "readline"):
        if not steps:
            raise BuildError(f"{lesson_id}/{task['id']}: {t} にはクエリが必要")
    else:
        raise BuildError(f"{lesson_id}/{task['id']}: 未知の type {t}")


def content_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(CONTENT.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(CONTENT).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:12]


def build():
    con = connect()
    levels = yaml.safe_load((CONTENT / "levels.yaml").read_text(encoding="utf-8"))
    glossary = yaml.safe_load((CONTENT / "glossary.yaml").read_text(encoding="utf-8"))
    lessons, seen_ids, errors = [], set(), []
    for path in sorted((CONTENT / "levels").glob("L*.yaml")):
        for lesson in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            lid = lesson["id"]
            if lid in seen_ids:
                errors.append(f"{lid}: レッスン ID 重複")
            seen_ids.add(lid)
            try:
                base_lines = lesson.get("query")
                if base_lines:
                    for i, l in enumerate(base_lines, 1):
                        l["id"] = f"q{i}"
                for ti, task in enumerate(lesson["tasks"], 1):
                    task["id"] = f"{lid}-t{ti}"
                    lines = task.get("query") or base_lines
                    if task.get("query"):
                        for i, l in enumerate(task["query"], 1):
                            l["id"] = f"q{i}"
                    steps = build_steps(con, f"{lid}/{task['id']}", lines) if lines else []
                    if steps:
                        task["steps"] = steps
                    check_task(lid, task, steps)
                    task["scored"] = task["type"] in SCORED
                lessons.append(lesson)
            except BuildError as e:
                errors.append(str(e))
            except duckdb.Error as e:
                errors.append(f"{lid}: SQL エラー: {e}")
    if errors:
        print("検証失敗:", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        sys.exit(1)
    payload = {
        "hash": content_hash(),
        "levels": levels,
        "glossary": glossary,
        "lessons": lessons,
    }
    js = "// 自動生成: python tools/build_lessons.py — 手で編集しない\nwindow.LESSONS = " + \
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.write_text(js, encoding="utf-8")
    # index.html の <script src="lessons.js?v=..."> を更新（キャッシュ避け）
    html_path = ROOT / "index.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        html_path.write_text(re.sub(r'lessons\.js\?v=[\w]+', f"lessons.js?v={payload['hash']}", html), encoding="utf-8")
    n_tasks = sum(len(l["tasks"]) for l in lessons)
    print(f"OK: {len(lessons)} レッスン / {n_tasks} 課題 → {OUT.name} ({OUT.stat().st_size // 1024} KB, hash {payload['hash']})")


def check():
    if not OUT.exists():
        print("lessons.js が無い", file=sys.stderr)
        sys.exit(1)
    m = re.search(r'"hash":"([0-9a-f]+)"', OUT.read_text(encoding="utf-8"))
    if not m or m.group(1) != content_hash():
        print("lessons.js が原稿より古い。python tools/build_lessons.py を実行", file=sys.stderr)
        sys.exit(1)
    print("OK: lessons.js は最新")


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
