from __future__ import annotations

from prosperity.quant.models import BudgetPolicy, GitScoutResult
from prosperity.settings import AppSettings


def allocate_quant_budget(settings: AppSettings, git: GitScoutResult) -> BudgetPolicy:
    quant = settings.quant
    has_strategy_commits = bool(git.candidate_strategy_files)
    has_any_commits = bool(git.commits)

    git_fraction = quant.git_budget_fraction
    reason = "default split"
    if has_strategy_commits:
        git_fraction = min(quant.max_git_budget_fraction, git_fraction + 0.10)
        reason = "new strategy-code commit found; git lane boosted but capped"
    elif has_any_commits:
        git_fraction = min(quant.max_git_budget_fraction, git_fraction + 0.03)
        reason = "non-strategy commit found; git lane receives light attention"

    direct_git_tests = 0
    git_variant_tests = 0
    if has_any_commits:
        direct_git_tests = max(quant.min_git_direct_tests, min(quant.max_git_strategy_tests, len(git.candidate_strategy_files)))
        git_variant_tests = quant.min_git_variant_tests if has_strategy_commits else 0

    return BudgetPolicy(
        git_fraction=git_fraction,
        raw_alpha_fraction=quant.raw_alpha_budget_fraction,
        champion_fraction=quant.champion_budget_fraction,
        structural_fraction=quant.structural_budget_fraction,
        direct_git_tests=direct_git_tests,
        git_variant_tests=git_variant_tests,
        alpha_strategy_tests=quant.max_alpha_strategies,
        reason=reason,
    )

