"""Audit live MySQL schema vs SQLAlchemy models. Read-only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault('OPLYRA_SKIP_DB_INIT', '1')

from sqlalchemy import create_engine, inspect, text
from app import create_app, db


def main():
    app = create_app('development')
    uri = os.environ['DATABASE_URL']
    engine = create_engine(uri)
    insp = inspect(engine)

    live_tables = set(insp.get_table_names())
    print('LIVE_TABLE_COUNT', len(live_tables))

    with engine.connect() as conn:
        has_alembic = 'alembic_version' in live_tables
        print('HAS_ALEMBIC_VERSION', has_alembic)
        if has_alembic:
            rows = conn.execute(text('SELECT version_num FROM alembic_version')).fetchall()
            print('ALEMBIC_VERSIONS', [r[0] for r in rows])

    if 'knowledge_search_logs' in live_tables:
        cols = {c['name'] for c in insp.get_columns('knowledge_search_logs')}
        print('KSL_COLUMNS', sorted(cols))
        print('HAS_search_query', 'search_query' in cols)
    else:
        print('KSL_MISSING_TABLE')

    for t in [
        'affiliate_networks', 'users', 'organizations', 'background_jobs',
        'tools', 'agents', 'knowledge_documents', 'tool_runs',
    ]:
        print(f'TABLE_{t}', t in live_tables)

    with app.app_context():
        model_tables = set(db.metadata.tables.keys())
        print('MODEL_TABLE_COUNT', len(model_tables))
        print('ONLY_IN_MODELS', sorted(model_tables - live_tables))
        print('ONLY_IN_LIVE', sorted(live_tables - model_tables - {'alembic_version'}))

        missing_cols = []
        type_mismatches = []
        for t in sorted(model_tables & live_tables):
            live_cols = {c['name']: c for c in insp.get_columns(t)}
            model_table = db.metadata.tables[t]
            for col in model_table.columns:
                if col.name not in live_cols:
                    missing_cols.append((t, col))
                # skip type deep compare for now

        print('MISSING_COL_COUNT', len(missing_cols))
        for t, col in missing_cols:
            nullable = 'NULL' if col.nullable else 'NOT NULL'
            default = col.server_default
            print(f'MISSING {t}.{col.name} type={col.type} {nullable} default={default}')

        # Missing indexes (name-level)
        missing_indexes = []
        for t in sorted(model_tables & live_tables):
            live_idx = {ix['name'] for ix in insp.get_indexes(t) if ix.get('name')}
            model_table = db.metadata.tables[t]
            for ix in model_table.indexes:
                if ix.name and ix.name not in live_idx:
                    missing_indexes.append((t, ix.name, list(ix.columns.keys())))
            # column index=True creates ix_<table>_<col> typically
            for col in model_table.columns:
                if col.index and not col.unique:
                    # sqlalchemy naming varies; check by columns
                    col_set = {col.name}
                    found = False
                    for ix in insp.get_indexes(t):
                        if set(ix.get('column_names') or []) == col_set:
                            found = True
                            break
                    # also unique constraints count
                    for uq in insp.get_unique_constraints(t):
                        if set(uq.get('column_names') or []) == col_set:
                            found = True
                            break
                    pk = insp.get_pk_constraint(t)
                    if set(pk.get('constrained_columns') or []) == col_set:
                        found = True
                    if not found:
                        missing_indexes.append((t, f'ix_{t}_{col.name}', [col.name]))

        # dedupe
        seen = set()
        uniq_missing_ix = []
        for item in missing_indexes:
            key = (item[0], tuple(item[2]))
            if key not in seen:
                seen.add(key)
                uniq_missing_ix.append(item)
        print('MISSING_INDEX_COUNT', len(uniq_missing_ix))
        for t, name, cols in uniq_missing_ix[:80]:
            print(f'MISSING_INDEX {t} {name} cols={cols}')


if __name__ == '__main__':
    main()
