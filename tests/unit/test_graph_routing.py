from orchestrator.agents.schemas import (
    ExecutionPlan,
    ReviewResult,
    ReviewVerdict,
    Subtask,
    SubtaskResult,
)
from orchestrator.graph.build_graph import (
    _find_next_ready_subtask,
    route_after_dispatch,
    route_after_human_review,
    route_after_planning,
    route_after_review,
    route_after_specialist,
)
from orchestrator.graph.build_graph import initial_state


def _subtask(id_: str, specialist: str = "research", depends_on: list[str] | None = None) -> Subtask:
    return Subtask(
        id=id_,
        description=f"do {id_}",
        assigned_specialist=specialist,
        depends_on=depends_on or [],
        required_inputs="n/a",
        expected_output_format="text",
        estimated_complexity=1,
    )


def test_find_next_ready_subtask_respects_dependencies():
    plan = ExecutionPlan(
        subtasks=[_subtask("st-1"), _subtask("st-2", depends_on=["st-1"])],
        confidence=0.9,
        reasoning="test",
    )
    # st-2 depends on st-1, which hasn't completed yet -> st-1 is next
    assert _find_next_ready_subtask(plan, {}).id == "st-1"

    # once st-1 is done, st-2 becomes ready
    done = {"st-1": SubtaskResult(subtask_id="st-1", output="ok")}
    assert _find_next_ready_subtask(plan, done).id == "st-2"

    # once both are done, nothing is ready
    done_all = {**done, "st-2": SubtaskResult(subtask_id="st-2", output="ok")}
    assert _find_next_ready_subtask(plan, done_all) is None


def test_route_after_planning_escalates_on_low_confidence():
    state = initial_state("t1", "do something")
    state["escalated"] = True
    assert route_after_planning(state) == "prepare_human_review"

    state["escalated"] = False
    assert route_after_planning(state) == "dispatch"


def test_route_after_dispatch_goes_to_synthesis_when_no_subtasks_left():
    plan = ExecutionPlan(subtasks=[_subtask("st-1")], confidence=0.9, reasoning="test")
    state = initial_state("t1", "do something")
    state["plan"] = plan
    state["current_subtask_id"] = None
    assert route_after_dispatch(state) == "synthesis"

    state["current_subtask_id"] = "st-1"
    assert route_after_dispatch(state) == "specialist_research"

    state["escalated"] = True
    assert route_after_dispatch(state) == "prepare_human_review"


def test_route_after_specialist_goes_to_review_unless_escalated():
    state = initial_state("t1", "do something")
    assert route_after_specialist(state) == "reviewer"

    state["escalated"] = True
    assert route_after_specialist(state) == "prepare_human_review"


def test_route_after_review_retries_on_rejection_then_escalates():
    plan = ExecutionPlan(subtasks=[_subtask("st-1")], confidence=0.9, reasoning="test")
    state = initial_state("t1", "do something")
    state["plan"] = plan
    state["current_subtask_id"] = "st-1"
    state["latest_review"] = ReviewResult(
        subtask_id="st-1", verdict=ReviewVerdict.REJECTED, quality_score=0.2, feedback="bad"
    )
    assert route_after_review(state) == "specialist_research"

    state["escalated"] = True
    assert route_after_review(state) == "prepare_human_review"


def test_route_after_human_review_maps_each_outcome():
    state = initial_state("t1", "do something")

    state["human_review_outcome"] = "resume_dispatch"
    assert route_after_human_review(state) == "dispatch"

    state["human_review_outcome"] = "resume_reviewer"
    assert route_after_human_review(state) == "reviewer"

    state["human_review_outcome"] = "finalize_and_dispatch"
    assert route_after_human_review(state) == "dispatch"

    state["human_review_outcome"] = "takeover_whole_task"
    assert route_after_human_review(state) == "terminal"

    state["human_review_outcome"] = "reject_task"
    assert route_after_human_review(state) == "terminal"
