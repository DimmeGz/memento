# Memory System Architecture для LLM

## Контекст

Система пам'яті для LLM з підтримкою кількох клієнтів (OpenWebUI, Cursor, Claude Code). Розгортається локально для обкатки, в майбутньому — окремий сервер для команди розробників.

## Стек

- **Векторна БД:** Qdrant (similarity search + payload filtering)
- **Реляційна БД:** PostgreSQL (сирі логи, метадані, черга для consolidator)

---

## Типи пам'яті

Комбінація трьох типів:

| Тип | Опис |
|---|---|
| **Episodic** | Конкретні факти з розмов |
| **Semantic** | Узагальнені факти про юзера/проєкт |
| **Procedural** | Правила, workflow-и, інструкції |

---

## Механізм пошуку

**Hybrid RAG:** BM25 + Vector Hybrid Search (Qdrant native) з Reciprocal Rank Fusion + core context в системному промпті.

- **BM25** — точний пошук по ключових словах (імена, версії, назви проектів)
- **Vector** — семантична схожість (синоніми, перефразування, концепції)
- **RRF** — злиття результатів: `score = 1/(k + rank_bm25) + 1/(k + rank_vector)`

---

## Сегрегація: user + project + scope

Ключ ізоляції — три поля в метаданих кожного факту:

| Поле | Значення |
|---|---|
| `user_id` | ідентифікатор користувача |
| `project_id` | ідентифікатор проекту або `null` |
| `scope` | `user` / `project` / `shared` |

### Scope логіка

**`user` scope** — факти про юзера незалежно від проекту:
- "Іванченко Олексій, senior backend"
- "Пише українською, UTC+2"

**`project` scope** — факти прив'язані до конкретного проекту:
- "Проект використовує FastAPI + SQLAlchemy"
- "Тести пишемо перед кодом"

**`shared` scope** — (опційно) спільне між проектами команди:
- "Команда використовує GitLab CI"
- "Стандарт іменування гілок: feature/TICKET-123"

### Recall filter — Private / Team розділення

При recall тягнемо з двох незалежних джерел:

```python
# Джерело 1 — Private: факти конкретного юзера
filter_user = {
    "scope": "user",
    "user_id": current_user_id
}

# Джерело 2 — Team: факти по проекту (user_id НЕ фільтруємо — видно факти колег)
filter_project = {
    "scope": "project",
    "project_id": current_project_id
}

results = merge_rrf(
    qdrant.search(..., filter=filter_user),
    qdrant.search(..., filter=filter_project)
)
```

> `scope=project` факти видно всій команді незалежно від `user_id`. Це дозволяє колегам бачити факти один одного по проекту.

---

## Структура метаданих факту в Qdrant

```json
{
  "user_id": "alice",
  "project_id": "proj_alpha",
  "scope": "project",
  "type": "procedural",
  "valid": true,
  "importance": 0.85,
  "decay_rate": 0.01,
  "embedding_model": "text-embedding-3-small",
  "created_at": "2026-04-28T10:00:00Z",
  "last_accessed_at": "2026-04-29T08:30:00Z",
  "source_session": "session_xyz"
}
```

| Поле | Призначення |
|---|---|
| `embedding_model` | При зміні моделі — дозволяє перегенерувати тільки старі вектори або фільтрувати при search |
| `last_accessed_at` | Оновлюється при кожному `recall`. База для майбутньої аналітики і decay по активності |

### Effective importance (враховує час)

```
effective_importance = importance * decay_factor(days_since_created)
```

---

## Сервіс №1 — MCP Memory Server (завжди online)

**Інтеграція:** MCP протокол — підключається до Cursor, Claude Code, OpenWebUI.

### MCP Tools

- `remember(fact, user_id, project_id, scope, type)` — явний тригер запису факту
- `recall(query, user_id, project_id)` — hybrid RAG пошук (user + project scope)
- `get_core_context(user_id, project_id)` — базові факти, завжди в промпті
- `log_message(message, role, user_id, project_id, session_id)` — логування сирих повідомлень

### `get_core_context()` — обмеження

Щоб уникнути перетворення на смітник, функція має жорсткі обмеження. Всі threshold-и виносяться в конфіг — без хардкоду:

```toml
# config.toml
[core_context]
user_limit          = 10    # max фактів про юзера
project_limit       = 10    # max фактів про проект
importance_threshold = 0.75 # мінімальна importance
```

```python
def get_core_context(user_id, project_id, cfg: CoreContextConfig):
    # Два незалежні запити — свій бюджет для кожного scope
    user_facts = qdrant.scroll(
        filter={
            "scope": "user",
            "user_id": user_id,
            "valid": True,
            "type": {"$in": ["semantic", "procedural"]},  # episodic виключаємо
            "importance": {"$gte": cfg.importance_threshold}
        },
        order_by="importance DESC",
        limit=cfg.user_limit
    )

    project_facts = qdrant.scroll(
        filter={
            "scope": "project",
            "project_id": project_id,
            "valid": True,
            "type": {"$in": ["semantic", "procedural"]},
            "importance": {"$gte": cfg.importance_threshold}
        },
        order_by="importance DESC",
        limit=cfg.project_limit
    )

    return user_facts + project_facts
```

Зовні — один інтерфейс. Всередині — два незалежні запити з окремими лімітами, щоб проектний контекст не витісняв юзерський і навпаки.

Коли прийде час розділити на `get_user_context()` і `get_project_context()` — просто розриваєш на два публічних методи. Нічого переписувати не треба.

> Episodic факти (конкретні епізоди з розмов) не потрібні в постійному контексті — тільки semantic і procedural.

### Флоу

1. Модель отримує повідомлення від юзера → відправляє його в сервіс
   - 1.1 Сервіс зберігає повідомлення в PostgreSQL (raw log, статус: `pending`)
   - 1.2 Сервіс робить similarity search в Qdrant з фільтром по `user_id` + `project_id`, повертає релевантний контекст
2. Модель формує відповідь → відправляє її в сервіс
   - 2.1 Сервіс дописує відповідь до того ж діалогу в PostgreSQL

---

## Сервіс №2 — Memory Consolidator (cron)

**Запуск:** за розкладом (наприклад, раз або кілька разів на день).

### Флоу

1. Взяти діалоги зі статусом `pending` з PostgreSQL, позначити як `in_progress`
2. Відправити діалог в LLM для аналізу — виділити факти, визначити `scope` і `type` кожного
3. **Дедуплікація перед insert:**

```python
results = qdrant.search(
    collection="facts",
    query_vector=new_embedding,
    filter={"user_id": user_id, "project_id": project_id, "scope": scope},
    limit=1
)

if results and results[0].score > 0.97:
    pass  # skip — факт вже є
else:
    qdrant.upsert(...)  # insert new fact
```

4. Позначити діалог в PostgreSQL як `processed` (НЕ видаляти одразу)

### Hard delete (окремий крон, раз на тиждень)

- Видаляти діалоги зі статусом `processed` старші N днів
- Видаляти факти з Qdrant з `valid: false` старші N днів

### Статуси діалогів в PostgreSQL

| Статус | Опис |
|---|---|
| `pending` | Збережено, ще не оброблено |
| `in_progress` | Взято consolidator-ом в обробку |
| `processed` | Факти витягнуті, безпечно видаляти |

---

## Загальна схема

```
Cursor / Claude Code / OpenWebUI
              ↓
    MCP Memory Server (#1)
    ├── remember()
    ├── recall()            → filter: Private (user) OR Team (project)
    ├── get_core_context()  → semantic+procedural, importance≥threshold, user_limit+project_limit (з конфігу)
    └── log_message()
       ↙                        ↘
 PostgreSQL                  Qdrant
 (raw logs)              (vectors + facts)
 status:                  metadata:
   pending                  user_id
   in_progress              project_id
   processed                scope
                            type
    ↑                       valid
 Memory                     importance
 Consolidator               embedding_model
   (#2 cron)                created_at
   └── similarity > 0.97?   last_accessed_at
         skip : insert
```

---

## Плани на майбутнє

### Інвалідація фактів

Повноцінна інвалідація замість простої дедуплікації. При виявленні суперечливого факту — позначати старий як `valid: false` замість вставки дубля. Потребує чіткого визначення критеріїв суперечності (через LLM або rule-based).

### Decay по активності

Прив'язати `effective_importance` до `last_accessed_at` замість (або разом з) `created_at`. Факти, до яких давно не зверталися, автоматично знижують вагу — релевантніше відображає реальну цінність.

### Аналітика використання

На основі `last_accessed_at` + `importance` будувати звіти: які факти реально використовуються, які "мертві", де є прогалини в пам'яті. Допоможе тюнити threshold-и і `max N` для `get_core_context`.

### Міграція embedding-моделей

При переході на нову модель — батчева перегенерація векторів тільки для записів зі старим `embedding_model`. Поле вже є в метаданих, залишається реалізувати migration job.

### Shared scope

Повноцінна реалізація `scope: shared` — факти спільні між проектами команди (стандарти, конвенції, загальні правила). Зараз поле передбачене в структурі, але логіка recall під нього не реалізована.

### Розділення get_core_context на два публічних методи

Коли кількість юзерів і проектів зросте — розбити на `get_user_context()` і `get_project_context()`. Внутрішня структура вже готова, потрібно тільки розкрити назовні. Дасть змогу кешувати юзерський контекст незалежно від проекту і викликати тільки потрібне.

### Розгортання на команду

Перехід від локального інстансу до shared сервера з авторизацією по `user_id`. Ізоляція приватних фактів (`scope: user`) на рівні API, а не тільки на рівні фільтрів Qdrant.
