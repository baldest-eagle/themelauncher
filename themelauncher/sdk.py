"""
ThemeSDK Facade — single entry point for the entire Theme Launcher SDK.

All 17 agents are lazily initialized on first access. Methods follow the
{"success": bool, "message": str, ...} return convention.
"""

import os
import threading
from typing import Any, Callable, Optional

from .agents.accessibility import AccessibilityChecker
from .agents.community_index import CommunityIndex
from .agents.compatibility import CompatibilityDetector
from .agents.converter import IconPackConverter
from .agents.diff_engine import DiffEngine
from .agents.directory_auditor import DirectoryAuditor
from .agents.manifest_generator import ManifestGenerator
from .agents.monitor import CrashMonitor
from .agents.pack_manager import PackManager
from .agents.packager import ThemePackager
from .agents.perf_analyzer import PerfAnalyzer
from .agents.recommender import Recommender
from .agents.scheduler import ThemeScheduler
from .agents.seven_tsp_extractor import SevenTSPExtractor
from .agents.snapshot import SnapshotAgent
from .agents.update_resilience import UpdateResilience
from .agents.variant_generator import VariantGenerator
from .agents.preview_bot import PreviewBot
from .core.logger import log


class ThemeSDK:
    """Unified facade for the Theme Launcher SDK."""

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path
        self._state_lock = threading.RLock()
        self._update_thread = None
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
        self._auditor: Optional[DirectoryAuditor] = None
        self._tsp_extractor: Optional[SevenTSPExtractor] = None
        self._preview_bot: Optional[PreviewBot] = None

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
        """Apply a full theme.

        Returns ``{success, message, components}`` where ``components`` is the
        per-component result map produced by the Applier. ``success`` is True
        only when every component reports success.
        """
        tm = self._load_theme_manager()
        if not tm:
            return {"success": False, "message": "Theme manager not available"}

        from core.applier import Applier
        applier = Applier(tm)
        with self._state_lock:
            results = applier.apply_full_theme(theme_name)

        # ``results`` is a per-component dict[str, dict]. Aggregate it into the
        # flat success/message/components contract callers expect.
        if isinstance(results, dict) and all(isinstance(v, dict) for v in results.values()):
            all_ok = all(v.get("success", False) for v in results.values()) if results else False
            if all_ok:
                message = f"Applied theme '{theme_name}' successfully."
            else:
                failed = [k for k, v in results.items() if not v.get("success", False)]
                message = f"Applied theme '{theme_name}' with failures: {', '.join(failed)}"
            return {"success": all_ok, "message": message, "components": results}
        # Defensive: if the applier already returned the flat shape, pass it through.
        if isinstance(results, dict) and "success" in results:
            return results
        return {"success": False, "message": f"Unexpected applier response: {results!r}", "components": results}

    # ------------------------------------------------------------------
    # Agent methods: Snapshot
    # ------------------------------------------------------------------

    def capture_snapshot(self) -> str:
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        with self._state_lock:
            return snap.capture_snapshot()

    def restore_snapshot(self, snapshot_id: Optional[str] = None) -> dict:
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        with self._state_lock:
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
        tm = self._load_theme_manager()
        detector = self._get_or_create("_compatibility", CompatibilityDetector, tm)
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
        """Start the update-resilience watcher.

        The callback (if provided) is invoked for *notification* only. The
        UpdateResilience agent itself always calls ``_handle_update`` to heal
        the system regardless of whether a callback is supplied — otherwise the
        auto-heal path would be unreachable whenever a callback is set.
        """
        tm = self._load_theme_manager()
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        agent = self._get_or_create("_update_resilience", UpdateResilience, tm, snap)
        notify_callback = callback or (lambda e: log.info("Update detected: %s", e))
        # Stop any prior watcher before starting a new one.
        self.stop_update_watcher()
        t = threading.Thread(
            target=agent.watch_for_updates,
            args=(notify_callback,),
            daemon=True,
            name="themelauncher-update-watcher",
        )
        self._update_thread = t
        t.start()

    def stop_update_watcher(self) -> None:
        """Stop the update-resilience watcher if it is running."""
        agent = self._update_resilience
        if agent is not None:
            try:
                agent.stop()
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("Failed to stop update watcher: %s", exc)
        t = self._update_thread
        self._update_thread = None
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=5)

    def check_integrity(self) -> dict:
        tm = self._load_theme_manager()
        snap = self._get_or_create("_snapshot", SnapshotAgent)
        agent = self._get_or_create("_update_resilience", UpdateResilience, tm, snap)
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

    def benchmark_component(self, component: str,
                            apply_fn: Optional[Callable[[], Any]] = None) -> dict:
        """Benchmark a single component.

        ``apply_fn`` (if provided) is invoked between the baseline and after
        measurements; without it the two measurements reflect the same state
        and the comparison is meaningless.
        """
        perf = self._get_or_create("_perf", PerfAnalyzer)
        baseline = perf.benchmark_baseline()
        if apply_fn is not None:
            try:
                apply_fn()
            except Exception as exc:
                log.exception("apply_fn raised during benchmark: %s", exc)
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
        if self._scheduler is not None:
            self._scheduler.stop()
        # Also stop the update watcher — they are commonly started together.
        self.stop_update_watcher()

    # ------------------------------------------------------------------
    # Agent methods: Packager
    # ------------------------------------------------------------------

    def package_theme(self, theme_name: str, output_dir: str,
                      manifest: Optional[dict] = None,
                      theme_path: Optional[str] = None) -> dict:
        pkg = self._get_or_create("_packager", ThemePackager)
        return pkg.package(theme_name, output_dir, manifest, theme_path)

    def publish_theme(self, theme_name: str, repo: Optional[str] = None) -> dict:
        log.warning("publish_theme('%s', repo=%r) is not implemented; use package_theme "
                    "to produce a shareable archive.", theme_name, repo)
        return {
            "success": False,
            "message": ("Publishing is not yet implemented. Use package_theme to "
                        "produce a shareable archive."),
        }

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

    # ------------------------------------------------------------------
    # Agent methods: Directory Auditor
    # ------------------------------------------------------------------

    def audit_themes(self) -> dict:
        tm = self._load_theme_manager()
        if not tm:
            return {"success": False, "message": "Theme manager not available"}
        themes_dir = tm.config.get("themes_directory", "")
        # Always construct a fresh auditor — config (themes_directory) may
        # change between calls and a cached instance would point at a stale dir.
        audit = DirectoryAuditor(themes_dir)
        return audit.audit_all()

    def standardize_theme(self, theme_name: str) -> dict:
        tm = self._load_theme_manager()
        if not tm:
            return {"success": False, "message": "Theme manager not available"}
        themes_dir = tm.config.get("themes_directory", "")
        audit = DirectoryAuditor(themes_dir)
        return audit.standardize_extensions(theme_name)

    # ------------------------------------------------------------------
    # Agent methods: 7TSP Extractor
    # ------------------------------------------------------------------

    def extract_7tsp(self, archive_path: str, theme_name: str) -> dict:
        tm = self._load_theme_manager()
        if not tm:
            return {"success": False, "message": "Theme manager not available"}
        themes_dir = tm.config.get("themes_directory", "")
        extractor = self._get_or_create("_tsp_extractor", SevenTSPExtractor)
        return extractor.full_pipeline(archive_path, theme_name, themes_dir)

    # ------------------------------------------------------------------
    # Agent methods: Preview Bot
    # ------------------------------------------------------------------

    def ingest_preview(self, file_path: str, theme_name: Optional[str] = None) -> dict:
        tm = self._load_theme_manager()
        if not tm:
            return {"success": False, "message": "Theme manager not available"}
        themes_dir = tm.config.get("themes_directory", "")
        bot = self._get_or_create("_preview_bot", PreviewBot, themes_dir)
        return bot.ingest_file(file_path, theme_name)