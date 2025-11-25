### 1. Базовый пример `StrChoices`

```python
from cortex.common.choices import StrChoices


class GraphStatus(StrChoices):
    DRAFT = ("draft", "Черновик", "Граф в работе, не используется в рантайме")
    ACTIVE = ("active", "Активен", "Текущий граф, по которому работают сессии")
    ARCHIVED = ("archived", "Архив", "Старые версии, только для просмотра")
```

Использование:

```python
# все значения
GraphStatus.values()
# ['draft', 'active', 'archived']

# все лейблы
GraphStatus.labels()
# ['Черновик', 'Активен', 'Архив']

# choices для Tortoise / форм
GraphStatus.choices()
# [('draft', 'Черновик'), ('active', 'Активен'), ('archived', 'Архив')]

# получить label по значению
GraphStatus.get_label("active")
# 'Активен'

# восстановить enum по значению
status = GraphStatus.from_value("draft")
assert status is GraphStatus.DRAFT
```

---

### 2. Базовый пример `IntChoices`

```python
from cortex.common.choices import IntChoices


class Priority(IntChoices):
    LOW = (10, "Низкий", "Фоновая обработка")
    NORMAL = (50, "Обычно", "Стандартный приоритет")
    HIGH = (90, "Высокий", "Срочные задачи")
```

Использование:

```python
Priority.values()         # [10, 50, 90]
Priority.labels()         # ['Низкий', 'Обычно', 'Высокий']
Priority.get_label(90)    # 'Высокий'
Priority.from_value(50)   # Priority.NORMAL
```

---

### 3. Использование с Tortoise ORM

#### 3.1. `StrChoices` + `CharEnumField`

```python
from tortoise import fields, models
from cortex.common.choices import StrChoices


class GraphStatus(StrChoices):
    DRAFT = ("draft", "Черновик", None)
    ACTIVE = ("active", "Активен", None)


class GraphDef(models.Model):
    id = fields.IntField(pk=True)
    key = fields.CharField(max_length=64, unique=True)

    status: fields.CharEnumField[GraphStatus] = fields.CharEnumField(
        GraphStatus,
        default=GraphStatus.DRAFT,
    )

    class Meta:
        table = "graph_defs"
```

В базе будут храниться строки `"draft"` / `"active"`, а в коде — `GraphStatus.DRAFT` и т.д.

```python
graph = await GraphDef.create(key="default", status=GraphStatus.ACTIVE)
assert graph.status is GraphStatus.ACTIVE
assert graph.status.value == "active"
assert graph.status.label == "Активен"
```

#### 3.2. `IntChoices` + `IntEnumField`

```python
from tortoise import fields, models
from cortex.common.choices import IntChoices


class QoSPriority(IntChoices):
    LOW = (10, "Низкий", None)
    NORMAL = (50, "Обычно", None)
    HIGH = (90, "Высокий", None)


class AgentDef(models.Model):
    id = fields.IntField(pk=True)
    key = fields.CharField(max_length=64, unique=True)

    priority: fields.IntEnumField[QoSPriority] = fields.IntEnumField(
        QoSPriority,
        default=QoSPriority.NORMAL,
    )
```

---

### 4. Использование с Pydantic v2

Просто аннотируешь поле enum-классом:

```python
from pydantic import BaseModel
from cortex.common.choices import StrChoices


class EventScope(StrChoices):
    LOCAL = ("local", "Локальное", "Внутри потока/агента")
    GLOBAL = ("global", "Глобальное", "Системное надпотоковое событие")


class EventDefSchema(BaseModel):
    id: int
    event_type: str
    scope: EventScope
```

Пример:

```python
data = {"id": 1, "event_type": "system.start", "scope": "global"}
event = EventDefSchema.model_validate(data)

assert event.scope is EventScope.GLOBAL
assert event.scope.label == "Глобальное"
```

Pydantic сам сделает JSON Schema с enum-значениями `["local", "global"]`.

---

Если резюмировать: `StrChoices`/`IntChoices` у тебя уже почти идеальный общий слой — они одинаково хорошо ложатся в Tortoise (`CharEnumField`/`IntEnumField`), Pydantic, и в UI-слой через `.choices()/.labels()/.get_label()`. Дальше это просто стандарт, от которого ты не будешь страдать через год.
