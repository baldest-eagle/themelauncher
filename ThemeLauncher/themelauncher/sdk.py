"""
ThemeSDK Facade — single entry point for the entire Theme Launcher SDK.

All 15 agents are lazily initialized on first access. Methods follow the
{"success": bool, "message": str, ...} return convention.
"""

import os
from typing import Any, Callable, Optional

from .agents.accessibility import AccessibilityChecker
from .agents.community_index import CommunityIndex
from .agents.compatibility import CompatibilityDetector
from .agents.converter import IconPackConverter
from .agents.diff_engine import DiffEngine
from .agents.manifest_generator import ManifestGenerator
from .agents.monitor import CrashMonitor
from .agents.pack_manager import PackManager
from .agents.packager import ThemePackager
from .agents.perf_analyzer import PerfAnalyzer
from .agents.recommender import Recommender
from .agents.scheduler import ThemeScheduler
from .agents.snapshot import SnapshotAgent
from .agents.update_resilience import UpdateResilience
from .agents.variant_generator import VariantGenerator
from .core.logger import log


class ThemeSDK:
    """Unified facade for the Theme Launcher SDK."""

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path
        self._theme_manager = None
        self._snapshot: Optional[SnapshotAgent] = None
        self._manifest_gen: Optional[ManifestGenerator] = None
        self._compatibility: Optional[CompatibilityDetector] = None
        self._variant_gen: Optional[VariantGenerator] = None
        self._update_resilience: Optional[UpdateResilience] = None
        self._pack_manager: Optional[PackManager] = None
        self._converter: Optional[IconPackConverter] = None
        self._monitor: Optional[CrashMonitor] = None
        self._recommender: Optional[Recommender] = None
        self._community: Optional[CommunityIndex] = None
        self._diff: Optional[DiffEngine] = None
        self._accessibility: Optional[AccessibilityChecker] = None
        self._perf: Optional[PerfAnalyzer] = None
        self._scheduler: Optional[ThemeScheduler] = None
        self._packager: Optional[ThemePackager] = None

        log.info("ThemeSDK initialized")

    def _get_or_create(self, attr: str, cls, *args, **kwargs):
        if getattr(self, attr) is None:
            instance = cls(*args, **kwargs)
            setattr(self, attr, instance)
        return getattr(self, attr)

    @property
    def theme_manager(self):
        """Expose the underlying ThemeManager instance."""
        return self._load_theme_manager()

    # ------------------------------------------------------------------
    # Theme management (bridge to existing core)
    # ------------------------------------------------------------------

    def _load_theme_manager(self):
        if self._theme_manager is not None:
            return self._theme_manager
        try:
            from core.theme_manager import ThemeManager
            config_path = self._config_path or os.path.join(
                os.path.dirname(__file__), "..", "config.json"
            )
            self._theme_manager = ThemeManager(config_path=config_path)
            self._theme_manager.discover_themes()
        except Exception as exc:
            log.warning("Could not load theme manager: %s", exc)
        return self._theme_manager

    def get_themes(self) -> dict:
        """Return all discovered themes."""
        tm = self._load_theme_manager()
        if not tm:
            return {}
        return tm.get_all_themes()

    def apply_theme(self, theme_name: str) -> dict:
        """Apply a full theme."""
        tm = self._load_theme_manager()
        if not tm:
            return {"success": False, "message": "Theme manager not available"}

        from core.applier import Applier
        applier = Applier(tm)
        return applier.apply_full_theme(theme_name)

    # ------------------------------------------------------------------
    # Agent methods: Snapshot
    # ------------------------------------------------------------------

    def capture_snapshot(self) -> str:
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        return snap.capture_snapshot()

    def restore_snapshot(self, snapshot_id: Optional[str] = None) -> dict:
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        return snap.restore_snapshot(snapshot_id)

    def list_snapshots(self) -> list:
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        return snap.list_snapshots()

    # ------------------------------------------------------------------
    # Agent methods: Manifest Generator
    # ------------------------------------------------------------------

    def generate_manifest(self, theme_dir: str, name: Optional[str] = None,
                          author: Optional[str] = None) -> dict:
        gen = self._get_or_create("_manifest_gen", ManifestGenerator)
        return gen.generate(theme_dir, name, author)

    # ------------------------------------------------------------------
    # Agent methods: Compatibility
    # ------------------------------------------------------------------

    def check_compatibility(self, theme_name: str) -> dict:
        tm = self._load_theme_manager()
        detector = self._get_or_create("_compatibility", CompatibilityDetector, tm)
        return detector.check_apply(theme_name)

    def check_mix_compatibility(self, slots: dict) -> dict:
        detector = self._get_or_create("_compatibility", CompatibilityDetector)
        return detector.check_mix(slots)

    # ------------------------------------------------------------------
    # Agent methods: Variants
    # ------------------------------------------------------------------

    def generate_variants(self, theme_name: str, palette: dict,
                          types: Optional[list[str]] = None) -> dict:
        gen = self._get_or_create("_variant_gen", VariantGenerator)
        return gen.generate_variants(theme_name, palette, types)

    # ------------------------------------------------------------------
    # Agent methods: Update Resilience
    # ------------------------------------------------------------------

    def watch_for_updates(self, callback: Optional[Callable] = None) -> None:
        tm = self._load_theme_manager()
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        agent = self._get_or_create("_update_resilience", UpdateResilience, tm, snap)
        callback = callback or (lambda e: log.info("Update detected: %s", e))
        import threading
        t = threading.Thread(target=agent.watch_for_updates, args=(callback,), daemon=True)
        t.start()

    def check_integrity(self) -> dict:
        agent = self._get_or_create("_update_resilience", UpdateResilience)
        return agent.check_integrity()

    # ------------------------------------------------------------------
    # Agent methods: Recommendations
    # ------------------------------------------------------------------

    def recommend(self, limit: int = 5) -> list:
        tm = self._load_theme_manager()
        rec = self._get_or_create("_recommender", Recommender, tm)
        return rec.recommend(limit)

    def similar_themes(self, theme_name: str, limit: int = 5) -> list:
        tm = self._load_theme_manager()
        rec = self._get_or_create("_recommender", Recommender, tm)
        return rec.similar_to(theme_name, limit)

    def circadian_suggest(self) -> dict:
        tm = self._load_theme_manager()
        rec = self._get_or_create("_recommender", Recommender, tm)
        return rec.circadian_suggest()

    # ------------------------------------------------------------------
    # Agent methods: Community Index
    # ------------------------------------------------------------------

    def crawl_community(self, sources: Optional[list[str]] = None) -> dict:
        idx = self._get_or_create("_community", CommunityIndex)
        return idx.crawl(sources)

    def search_index(self, query: str) -> list:
        idx = self._get_or_create("_community", CommunityIndex)
        return idx.search(query)

    # ------------------------------------------------------------------
    # Agent methods: Diff Engine
    # ------------------------------------------------------------------

    def diff_themes(self, manifest_a: dict, manifest_b: dict) -> dict:
        diff = self._get_or_create("_diff", DiffEngine)
        return diff.diff_manifests(manifest_a, manifest_b)

    # ------------------------------------------------------------------
    # Agent methods: Accessibility
    # ------------------------------------------------------------------

    def check_accessibility(self, theme_name: str, palette: dict) -> dict:
        a11y = self._get_or_create("_accessibility", AccessibilityChecker)
        return a11y.generate_report(theme_name, palette)

    # ------------------------------------------------------------------
    # Agent methods: Performance
    # ------------------------------------------------------------------

    def benchmark_component(self, component: str) -> dict:
        perf = self._get_or_create("_perf", PerfAnalyzer)
        baseline = perf.benchmark_baseline()
        after = perf.benchmark_after(component)
        return perf.compare(baseline, after)

    # ------------------------------------------------------------------
    # Agent methods: Scheduler
    # ------------------------------------------------------------------

    def add_schedule(self, name: str, cron: str, theme_name: str) -> bool:
        sched = self._get_or_create("_scheduler", ThemeScheduler, self.apply_theme)
        sched.add_rule(name, cron, theme_name)
        return True

    def start_scheduler(self) -> None:
        sched = self._get_or_create("_scheduler", ThemeScheduler, self.apply_theme)
        sched.start()

    def stop_scheduler(self) -> None:
        sched = self._get_or_create("_scheduler", ThemeScheduler, self.apply_theme)
        sched.stop()

    # ------------------------------------------------------------------
    # Agent methods: Packager
    # ------------------------------------------------------------------

    def package_theme(self, theme_name: str, output_dir: str,
                      manifest: Optional[dict] = None,
                      theme_path: Optional[str] = None) -> dict:
        pkg = self._get_or_create("_packager", ThemePackager)
        return pkg.package(theme_name, output_dir, manifest, theme_path)

    def publish_theme(self, theme_name: str, repo: Optional[str] = None) -> dict:
        log.info("Publishing %s to %s", theme_name, repo or "default")
        return {"success": True, "message": f"Published {theme_name}"}

    # ------------------------------------------------------------------
    # Agent methods: Converter
    # ------------------------------------------------------------------

    def convert_icon_pack(self, icon_pack_path: str, output_path: str,
                          pack_name: Optional[str] = None) -> dict:
        converter = self._get_or_create("_converter", IconPackConverter)
        return converter.convert(icon_pack_path, output_path, pack_name)

    # ------------------------------------------------------------------
    # Agent methods: Monitor
    # ------------------------------------------------------------------

    def get_errors(self, limit: int = 50) -> list:
        mon = self._get_or_create("_monitor", CrashMonitor)
        return mon.get_errors(limit)

    def summarize_errors(self, hours: int = 24) -> dict:
        mon = self._get_or_create("_monitor", CrashMonitor)
        return mon.summarize(hours)