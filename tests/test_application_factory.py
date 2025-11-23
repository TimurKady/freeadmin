from types import SimpleNamespace

from fastapi import FastAPI

from freeadmin.application import ApplicationFactory
from freeadmin.core.runtime.hub import admin_site


class DummyLifecycle:
    def __init__(self) -> None:
        self.bind_calls = 0
        self.adapter_name = "dummy-adapter"

    def bind(self, app: FastAPI) -> None:
        self.bind_calls += 1
        app.state.lifecycle_bound = True


class DummyORMConfig:
    def __init__(self, lifecycle: DummyLifecycle) -> None:
        self._lifecycle = lifecycle

    def create_lifecycle(self) -> DummyLifecycle:
        return self._lifecycle


class DummyBootManager:
    def __init__(self) -> None:
        self.calls: list[tuple[FastAPI, str | None, list[str] | None]] = []

    def init(
        self,
        app: FastAPI,
        *,
        adapter: str | None = None,
        packages: list[str] | None = None,
    ) -> None:
        self.calls.append((app, adapter, list(packages) if packages else None))


class DummyRouterManager:
    def __init__(self) -> None:
        self.app: FastAPI | None = None
        self.site = None

    def mount(self, app: FastAPI, site) -> None:  # type: ignore[override]
        self.app = app
        self.site = site


async def sample_startup() -> None:
    pass


async def sample_shutdown() -> None:
    pass


def test_application_factory_builds_configured_app() -> None:
    lifecycle = DummyLifecycle()
    orm_config = DummyORMConfig(lifecycle)
    boot_manager = DummyBootManager()
    router_manager = DummyRouterManager()
    settings = SimpleNamespace(project_title="Test Admin")

    factory = ApplicationFactory(
        settings=settings,
        orm_config=orm_config,  # type: ignore[arg-type]
        router_manager=router_manager,
        boot_manager=boot_manager,  # type: ignore[arg-type]
    )
    factory.register_packages(["custom.apps"])
    factory.register_packages(["pages"])  # Duplicate should be ignored.
    factory.register_startup_hook(sample_startup)
    factory.register_shutdown_hook(sample_shutdown)

    app = factory.build()

    assert isinstance(app, FastAPI)
    assert app.title == "Test Admin"
    assert lifecycle.bind_calls == 1
    assert getattr(app.state, "lifecycle_bound", False) is True
    assert boot_manager.calls
    call_app, adapter_name, packages = boot_manager.calls[0]
    assert call_app is app
    assert adapter_name == lifecycle.adapter_name
    assert packages == ["apps", "pages", "custom.apps"]
    assert router_manager.app is app
    assert router_manager.site is admin_site
    assert sample_startup in app.router.on_startup
    assert sample_shutdown in app.router.on_shutdown
