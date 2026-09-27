"""grant privileges and enable row level security

Revision ID: d6cb2637f739
Revises: 2058c667ebfe
Create Date: 2026-09-24 14:03:55.165407

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6cb2637f739"
down_revision: str | Sequence[str] | None = "2058c667ebfe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# docs/architecture.md, раздел 4.5. Роли создаёт окружение (docker-compose
# `configs`/`init_db_roles` локально, администратор БД в staging/production),
# эта миграция только выдаёт права и включает RLS. Если роли не существует,
# миграция падает с понятным сообщением, а не создаёт роль сама.
_APP_ROLE = "finplan_app"
_WORKER_ROLE = "finplan_worker"
_ROLES = (_APP_ROLE, _WORKER_ROLE)
_OWNED_TABLES = ("users", "accounts", "categories", "transactions")
_SEARCH_FUNCTION = "find_user_by_telegram_id"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
                RAISE EXCEPTION
                    'role "{_APP_ROLE}" does not exist; create it before running '
                    'this migration (docs/architecture.md, section 4.5)';
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{_WORKER_ROLE}') THEN
                RAISE EXCEPTION
                    'role "{_WORKER_ROLE}" does not exist; create it before running '
                    'this migration (docs/architecture.md, section 4.5)';
            END IF;
        END
        $$;
        """
    )

    # GRANT на существующие объекты — раздел 4.5, таблица ролей: finplan_app
    # и finplan_worker получают одинаковые права на пользовательские таблицы.
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(_OWNED_TABLES)} TO {', '.join(_ROLES)}"
    )
    # currencies — справочник (раздел 4.1, 4.5): не пользовательская таблица,
    # RLS не получает и права ограничены чтением, в отличие от _OWNED_TABLES.
    op.execute(f"GRANT SELECT ON currencies TO {', '.join(_ROLES)}")
    op.execute(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {', '.join(_ROLES)}")

    # ALTER DEFAULT PRIVILEGES без `FOR ROLE` действует для той роли, что
    # выполняет саму команду, — то есть для владельца схемы, под которым
    # идут миграции (роль `finplan` в 4.5; в тестах — учётная запись
    # testcontainers), и распространяется на таблицы, которые появятся
    # позже. Справочники вроде будущей `exchange_rates` сузят себе права
    # явным `GRANT` в собственной миграции — как currencies выше.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {', '.join(_ROLES)}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO {', '.join(_ROLES)}"
    )

    # RLS на пользовательских таблицах (раздел 4.5). FORCE не включается:
    # под FORCE функция SECURITY DEFINER ниже тоже перестанет видеть строки.
    op.execute("ALTER TABLE accounts ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY p_accounts_owner ON accounts "
        "USING (user_id = current_setting('app.user_id', true)::uuid)"
    )
    op.execute("ALTER TABLE categories ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY p_categories_owner ON categories "
        "USING (user_id = current_setting('app.user_id', true)::uuid)"
    )
    op.execute("ALTER TABLE transactions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY p_transactions_owner ON transactions "
        "USING (user_id = current_setting('app.user_id', true)::uuid)"
    )

    # users: политика по собственному ключу, дословно по разделу 4.5, с
    # явным WITH CHECK (в отличие от политик выше, документ приводит его
    # отдельно, хотя для одной команды USING и так служит проверкой INSERT).
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY p_users_self ON users "
        "USING (id = current_setting('app.user_id', true)::uuid) "
        "WITH CHECK (id = current_setting('app.user_id', true)::uuid)"
    )

    # Поиск по telegram_id до того, как пользователь известен (app.user_id
    # не задан) — только через SECURITY DEFINER функцию, раздел 4.5,
    # дословно. REVOKE ALL FROM PUBLIC закрывает функцию от прочих ролей;
    # GRANT EXECUTE выдаётся только finplan_app по заданию подзадачи 8b.
    op.execute(
        f"""
        CREATE FUNCTION {_SEARCH_FUNCTION}(p_telegram_id bigint)
            RETURNS SETOF users
            LANGUAGE sql STABLE SECURITY DEFINER
            SET search_path = public, pg_temp
        AS $$ SELECT * FROM users WHERE telegram_id = p_telegram_id $$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_SEARCH_FUNCTION}(bigint) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_SEARCH_FUNCTION}(bigint) TO {_APP_ROLE}")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_SEARCH_FUNCTION}(bigint) FROM {_APP_ROLE}")
    op.execute(f"DROP FUNCTION IF EXISTS {_SEARCH_FUNCTION}(bigint)")

    op.execute("DROP POLICY IF EXISTS p_users_self ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS p_transactions_owner ON transactions")
    op.execute("ALTER TABLE transactions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS p_categories_owner ON categories")
    op.execute("ALTER TABLE categories DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS p_accounts_owner ON accounts")
    op.execute("ALTER TABLE accounts DISABLE ROW LEVEL SECURITY")

    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE USAGE ON SEQUENCES FROM {', '.join(_ROLES)}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {', '.join(_ROLES)}"
    )
    op.execute(f"REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM {', '.join(_ROLES)}")
    op.execute(f"REVOKE SELECT ON currencies FROM {', '.join(_ROLES)}")
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {', '.join(_OWNED_TABLES)} "
        f"FROM {', '.join(_ROLES)}"
    )
