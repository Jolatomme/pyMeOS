# Lazy imports so that Qt-free modules (draw, result, speaker, automation)
# can be imported without PySide6 installed.
from .result     import evaluate_card, compute_class_results, compute_all_results, compute_team_results
from .draw       import assign_start_times, assign_pursuit_starts
from .speaker    import SpeakerController
from .automation import AutomationController, AutoTaskConfig, TaskType

# CompetitionController needs Qt – import only if available
try:
    from .competition import CompetitionController
    __all__ = [
        "CompetitionController",
        "evaluate_card", "compute_class_results",
        "compute_all_results", "compute_team_results",
        "assign_start_times", "assign_pursuit_starts",
        "SpeakerController",
        "AutomationController", "AutoTaskConfig", "TaskType",
    ]
except ImportError:
    __all__ = [
        "evaluate_card", "compute_class_results",
        "compute_all_results", "compute_team_results",
        "assign_start_times", "assign_pursuit_starts",
        "SpeakerController",
        "AutomationController", "AutoTaskConfig", "TaskType",
    ]
