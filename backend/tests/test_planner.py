import pytest
from models import CriteriaInput
from services.planner import Plan, Planner, PlanStep


class TestPlanner:
    @pytest.mark.asyncio
    async def test_create_plan_basic(self):
        planner = Planner()
        criteria = CriteriaInput(direction="Python", city="Москва")
        plan = await planner.create_plan(criteria, pool_size=0)
        assert isinstance(plan, Plan)
        assert plan.goal
        assert len(plan.steps) >= 2
        assert plan.confidence > 0

    @pytest.mark.asyncio
    async def test_create_plan_with_existing_pool(self):
        planner = Planner()
        criteria = CriteriaInput(direction="Python")
        plan = await planner.create_plan(criteria, pool_size=10)
        assert len(plan.steps) >= 2
        assert plan.steps[0].action == "score_vacancies"

    @pytest.mark.asyncio
    async def test_create_plan_with_memory_patterns(self):
        planner = Planner()
        criteria = CriteriaInput(direction="Python")
        patterns = {"search_vacancies": {"count": 5, "avg_quality": 7.0}}
        plan = await planner.create_plan(criteria, pool_size=0, memory_patterns=patterns)
        assert plan is not None

    @pytest.mark.asyncio
    async def test_replan_after_search_failure(self):
        planner = Planner()
        criteria = CriteriaInput(direction="Python")
        plan = await planner.create_plan(criteria, pool_size=0)
        replanned = await planner.replan(plan, "search timeout", pool_size=5, criteria=criteria)
        assert isinstance(replanned, Plan)
        assert "timeout" in replanned.goal.lower() or "Replan" in replanned.goal
        assert len(replanned.steps) >= 2

    @pytest.mark.asyncio
    async def test_replan_after_low_score(self):
        planner = Planner()
        criteria = CriteriaInput(direction="Python")
        plan = await planner.create_plan(criteria, pool_size=10)
        replanned = await planner.replan(plan, "мало результатов", pool_size=5, criteria=criteria)
        assert replanned is not None
        assert len(replanned.steps) >= 2

    def test_plan_current_step(self):
        plan = Plan(goal="test", steps=[
            PlanStep(step_id=0, action="search", status="completed"),
            PlanStep(step_id=1, action="score", status="pending"),
        ])
        current = plan.current_step()
        assert current is not None
        assert current.step_id == 1

    def test_plan_complete_step(self):
        plan = Plan(goal="test", steps=[
            PlanStep(step_id=0, action="search", status="pending"),
        ])
        plan.complete_step(0, {"found": 10})
        assert plan.steps[0].status == "completed"
        assert plan.steps[0].result == {"found": 10}

    def test_plan_fail_step(self):
        plan = Plan(goal="test", steps=[
            PlanStep(step_id=0, action="search", status="pending"),
        ])
        plan.fail_step(0, "timeout")
        assert plan.steps[0].status == "failed"

    def test_plan_is_finished(self):
        plan = Plan(goal="test", steps=[
            PlanStep(step_id=0, action="search", status="completed"),
            PlanStep(step_id=1, action="score", status="failed"),
        ])
        assert plan.is_finished() is True

    def test_plan_not_finished(self):
        plan = Plan(goal="test", steps=[
            PlanStep(step_id=0, action="search", status="completed"),
            PlanStep(step_id=1, action="score", status="pending"),
        ])
        assert plan.is_finished() is False

    def test_get_plan_history(self):
        planner = Planner()
        assert len(planner.get_plan_history()) == 0

    def test_get_last_plan(self):
        planner = Planner()
        assert planner.get_last_plan() is None
