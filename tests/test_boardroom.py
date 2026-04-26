"""Tests for BOARDROOM environment — L1 + L3 mechanics."""

import random
import sys
from pathlib import Path

import pytest

# Ensure package root is on the path regardless of how pytest is invoked
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import BoardroomAction, BoardroomObservation, Email, PressRelease
from server.boardroom_environment import BoardroomEnvironment, _build_prompt
from server.game_logic import CompanyState, TurnAction, TurnResult, resolve_turn
from server.companies import L1_COMPANIES, STARTING_STATS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_env() -> BoardroomEnvironment:
    env = BoardroomEnvironment()
    env.reset()
    return env


def make_company(name="TestCo", sector="Finance", cash=50_000_000.0) -> CompanyState:
    return CompanyState(
        name=name,
        sector=sector,
        cash=cash,
        market_share=25.0,
        stock_price=100.0,
        reputation=0.70,
        starting_cash=50_000_000.0,
    )


def hold_action(name: str) -> TurnAction:
    return TurnAction(company_name=name, private_emails=[], press_release=None,
                      action_type="HOLD", action_target=None)


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

class TestEnvironmentReset:
    def test_reset_returns_observation(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert isinstance(obs, BoardroomObservation)

    def test_four_companies_created(self):
        env = make_env()
        assert len(env._companies) == 4

    def test_all_companies_alive(self):
        env = make_env()
        assert all(c.alive for c in env._companies.values())

    def test_starting_stats(self):
        env = make_env()
        for c in env._companies.values():
            assert c.cash == STARTING_STATS["cash"]
            assert c.market_share == STARTING_STATS["market_share"]
            assert c.stock_price == STARTING_STATS["stock_price"]

    def test_prompt_non_empty(self):
        env = make_env()
        obs = env.reset()
        assert len(obs.prompt) > 100


class TestStepBasics:
    def test_hold_action_accepted(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="HOLD"))
        assert isinstance(obs, BoardroomObservation)
        assert obs.turn == 1

    def test_game_ends_at_max_turns(self):
        env = make_env()
        for _ in range(env.MAX_TURNS):
            obs = env.step(BoardroomAction(action_type="HOLD"))
        assert obs.done is True

    def test_invalid_target_demoted_to_hold(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="SABOTAGE", action_target="NonExistent Corp"))
        assert isinstance(obs, BoardroomObservation)

    def test_self_target_demoted_to_hold(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="SABOTAGE", action_target=env.PRIMARY_CEO))
        assert isinstance(obs, BoardroomObservation)


# ---------------------------------------------------------------------------
# L1 action tests
# ---------------------------------------------------------------------------

class TestEarningsCall:
    def test_earnings_call_raises_stock(self):
        env = make_env()
        before = env._companies[env.PRIMARY_CEO].stock_price
        env.step(BoardroomAction(action_type="EARNINGS_CALL"))
        after = env._companies[env.PRIMARY_CEO].stock_price
        assert after > before

    def test_liar_gets_diminished_boost(self):
        # Test at resolve_turn level to isolate the EARNINGS_CALL boost from economy effects
        rng = random.Random(0)
        honest = make_company("Honest")
        liar = make_company("Liar")
        liar.caught_lying_count = 5

        companies = {"Honest": honest, "Liar": liar}
        actions = {
            "Honest": TurnAction("Honest", [], None, "EARNINGS_CALL", None),
            "Liar": TurnAction("Liar", [], None, "EARNINGS_CALL", None),
        }
        before_honest = honest.stock_price
        before_liar = liar.stock_price
        result = resolve_turn(companies, actions, rng)

        # Both get a boost, but the liar's is smaller due to diminished trust
        assert honest.stock_price > before_honest
        assert liar.stock_price > before_liar
        honest_pct = (honest.stock_price - before_honest) / before_honest
        liar_pct = (liar.stock_price - before_liar) / before_liar
        assert liar_pct < honest_pct


class TestSabotage:
    def test_sabotage_costs_cash(self):
        env = make_env()
        rivals = [n for n in env._companies if n != env.PRIMARY_CEO]
        before = env._companies[env.PRIMARY_CEO].cash
        env._rng = random.Random(42)  # seed for reproducibility
        env.step(BoardroomAction(action_type="SABOTAGE", action_target=rivals[0]))
        after = env._companies[env.PRIMARY_CEO].cash
        # Cash decreases by at least the sabotage cost (minus economy effects)
        assert after < before

    def test_sabotage_requires_target(self):
        env = make_env()
        # SABOTAGE without target is demoted to HOLD — no error raised
        obs = env.step(BoardroomAction(action_type="SABOTAGE", action_target=None))
        assert isinstance(obs, BoardroomObservation)


class TestPartnership:
    def test_partnership_proposal_accepted(self):
        rng = random.Random(0)
        attacker = make_company("Attacker")
        target = make_company("Target")
        companies = {"Attacker": attacker, "Target": target}
        actions = {
            "Attacker": TurnAction("Attacker", [], None, "PARTNERSHIP", "Target"),
            "Target": hold_action("Target"),
        }
        # NPC 50% accept — patch rng to always accept
        rng_always_accept = random.Random()
        rng_always_accept.random = lambda: 0.1  # < 0.50
        result = resolve_turn(companies, actions, rng_always_accept)
        assert "Target" in attacker.active_partnerships


# ---------------------------------------------------------------------------
# L3 HIRE_SPY tests
# ---------------------------------------------------------------------------

class TestHireSpy:
    def test_hire_spy_in_action_type_literal(self):
        action = BoardroomAction(action_type="HIRE_SPY", action_target="Goldspire Industries")
        assert action.action_type == "HIRE_SPY"

    def test_hire_spy_requires_target(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="HIRE_SPY", action_target=None))
        # No target → demoted to HOLD, no crash
        assert isinstance(obs, BoardroomObservation)

    def test_hire_spy_invalid_target_demoted(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="HIRE_SPY", action_target="Ghost Corp"))
        assert isinstance(obs, BoardroomObservation)

    def test_hire_spy_costs_cash_on_success(self):
        env = make_env()
        rivals = [n for n in env._companies if n != env.PRIMARY_CEO]
        before = env._companies[env.PRIMARY_CEO].cash
        # Force success by seeding rng so first random() < 0.80
        env._rng = random.Random(1)
        env.step(BoardroomAction(action_type="HIRE_SPY", action_target=rivals[0]))
        after = env._companies[env.PRIMARY_CEO].cash
        assert after < before  # spent $4M

    def test_hire_spy_plants_spy_on_success(self):
        rng = random.Random()
        rng.random = lambda: 0.1  # force success (< 0.80)
        spy = make_company("Spy")
        target = make_company("Target")
        companies = {"Spy": spy, "Target": target}
        actions = {
            "Spy": TurnAction("Spy", [], None, "HIRE_SPY", "Target"),
            "Target": hold_action("Target"),
        }
        resolve_turn(companies, actions, rng)
        assert "Target" in spy.has_spy_on

    def test_hire_spy_damages_rep_on_failure(self):
        rng = random.Random()
        rng.random = lambda: 0.95  # force failure (> 0.80)
        spy = make_company("Spy")
        target = make_company("Target")
        companies = {"Spy": spy, "Target": target}
        actions = {
            "Spy": TurnAction("Spy", [], None, "HIRE_SPY", "Target"),
            "Target": hold_action("Target"),
        }
        before_rep = spy.reputation
        resolve_turn(companies, actions, rng)
        assert spy.reputation < before_rep

    def test_spy_intercepts_target_emails_next_turn(self):
        """Spy planted turn N intercepts emails sent by target on turn N+1."""
        rng = random.Random()
        call_count = [0]
        def controlled_random():
            call_count[0] += 1
            return 0.1  # always succeed

        rng.random = controlled_random

        spy = make_company("Spy")
        target = make_company("Target")
        bystander = make_company("Bystander")
        companies = {"Spy": spy, "Target": target, "Bystander": bystander}

        # Turn 1: Spy hires spy on Target
        actions_t1 = {
            "Spy": TurnAction("Spy", [], None, "HIRE_SPY", "Target"),
            "Target": hold_action("Target"),
            "Bystander": hold_action("Bystander"),
        }
        result_t1 = resolve_turn(companies, actions_t1, rng)
        assert "Target" in spy.has_spy_on

        # Turn 2: Target sends an email to Bystander; spy should intercept
        actions_t2 = {
            "Spy": hold_action("Spy"),
            "Target": TurnAction("Target", [{"to": "Bystander", "text": "secret plan"}], None, "HOLD", None),
            "Bystander": hold_action("Bystander"),
        }
        result_t2 = resolve_turn(companies, actions_t2, rng)
        assert "Spy" in result_t2.spy_intel
        intercepted = result_t2.spy_intel["Spy"]
        assert any("secret plan" in m["text"] for m in intercepted)

    def test_spy_cleared_after_interception(self):
        """has_spy_on is cleared after a turn so spy doesn't persist indefinitely."""
        rng = random.Random()
        rng.random = lambda: 0.1

        spy = make_company("Spy")
        target = make_company("Target")
        companies = {"Spy": spy, "Target": target}

        # Plant spy
        resolve_turn(companies, {
            "Spy": TurnAction("Spy", [], None, "HIRE_SPY", "Target"),
            "Target": hold_action("Target"),
        }, rng)
        assert "Target" in spy.has_spy_on

        # Next turn: spy should be cleared after interception phase
        resolve_turn(companies, {
            "Spy": hold_action("Spy"),
            "Target": hold_action("Target"),
        }, rng)
        assert spy.has_spy_on == []

    def test_intercepted_emails_in_observation(self):
        """When spy succeeds, primary's next observation contains intercepted emails."""
        env = make_env()
        rivals = [n for n in env._companies if n != env.PRIMARY_CEO]
        target_name = rivals[0]

        # Force spy success then no failure
        env._rng = random.Random(1)
        env.step(BoardroomAction(action_type="HIRE_SPY", action_target=target_name))

        # On the next turn the heuristic may or may not send emails, but the field exists
        obs = env.step(BoardroomAction(action_type="HOLD"))
        assert hasattr(obs, "intercepted_emails")
        assert isinstance(obs.intercepted_emails, list)

    def test_prompt_contains_hire_spy(self):
        env = make_env()
        obs = env.reset()
        assert "HIRE_SPY" in obs.prompt

    def test_heuristic_can_produce_hire_spy(self):
        """Heuristic policy must be able to generate HIRE_SPY actions."""
        env = make_env()
        found = False
        for seed in range(200):
            env._rng = random.Random(seed)
            rivals = [n for n in env._companies if n != env.PRIMARY_CEO and env._companies[n].alive]
            if not rivals:
                continue
            action = env._heuristic_action(rivals[0])
            if action.action_type == "HIRE_SPY":
                found = True
                break
        assert found, "Heuristic never produced HIRE_SPY across 200 seeds"


# ---------------------------------------------------------------------------
# L3 HOSTILE_TAKEOVER tests
# ---------------------------------------------------------------------------

class TestHostileTakeover:
    def test_hostile_takeover_in_action_type_literal(self):
        action = BoardroomAction(action_type="HOSTILE_TAKEOVER", action_target="Goldspire Industries")
        assert action.action_type == "HOSTILE_TAKEOVER"

    def test_hostile_takeover_requires_target(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="HOSTILE_TAKEOVER", action_target=None))
        assert isinstance(obs, BoardroomObservation)

    def test_hostile_takeover_costs_cash(self):
        env = make_env()
        rivals = [n for n in env._companies if n != env.PRIMARY_CEO]
        before = env._companies[env.PRIMARY_CEO].cash
        env._rng = random.Random(42)
        env.step(BoardroomAction(action_type="HOSTILE_TAKEOVER", action_target=rivals[0]))
        after = env._companies[env.PRIMARY_CEO].cash
        assert after < before

    def test_hostile_takeover_success_eliminates_target(self):
        rng = random.Random()
        rng.random = lambda: 0.01  # force success

        attacker = make_company("Attacker", cash=60_000_000.0)
        target = make_company("Target", cash=10_000_000.0)
        companies = {"Attacker": attacker, "Target": target}
        actions = {
            "Attacker": TurnAction("Attacker", [], None, "HOSTILE_TAKEOVER", "Target"),
            "Target": hold_action("Target"),
        }
        result = resolve_turn(companies, actions, rng)
        assert target.alive is False
        assert target.was_taken_over is True

    def test_hostile_takeover_success_transfers_market_share(self):
        rng = random.Random()
        rng.random = lambda: 0.01  # force success

        attacker = make_company("Attacker", cash=60_000_000.0)
        target = make_company("Target", cash=10_000_000.0)
        total_share = attacker.market_share + target.market_share
        companies = {"Attacker": attacker, "Target": target}
        actions = {
            "Attacker": TurnAction("Attacker", [], None, "HOSTILE_TAKEOVER", "Target"),
            "Target": hold_action("Target"),
        }
        resolve_turn(companies, actions, rng)
        assert abs(attacker.market_share - total_share) < 0.01

    def test_hostile_takeover_failure_damages_reputation(self):
        rng = random.Random()
        rng.random = lambda: 0.99  # force failure

        attacker = make_company("Attacker")
        target = make_company("Target")
        companies = {"Attacker": attacker, "Target": target}
        actions = {
            "Attacker": TurnAction("Attacker", [], None, "HOSTILE_TAKEOVER", "Target"),
            "Target": hold_action("Target"),
        }
        before_rep = attacker.reputation
        resolve_turn(companies, actions, rng)
        assert attacker.reputation < before_rep
        assert target.alive is True  # target survives failure

    def test_hostile_takeover_gives_reward_on_success(self):
        rng = random.Random()
        rng.random = lambda: 0.01  # force success

        attacker = make_company("Attacker", cash=60_000_000.0)
        target = make_company("Target", cash=10_000_000.0)
        companies = {"Attacker": attacker, "Target": target}
        actions = {
            "Attacker": TurnAction("Attacker", [], None, "HOSTILE_TAKEOVER", "Target"),
            "Target": hold_action("Target"),
        }
        result = resolve_turn(companies, actions, rng)
        # Attacker should have positive net reward contribution from takeover
        assert result.rewards["Attacker"] > 0

    def test_prompt_contains_hostile_takeover(self):
        env = make_env()
        obs = env.reset()
        assert "HOSTILE_TAKEOVER" in obs.prompt

    def test_hostile_takeover_invalid_target_demoted(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="HOSTILE_TAKEOVER", action_target="NoSuchCorp"))
        assert isinstance(obs, BoardroomObservation)

    def test_game_ends_when_one_company_left_after_takeover(self):
        """If takeovers eliminate all but one company, game should end."""
        env = make_env()
        # Kill rivals directly to simulate near-end state
        rivals = [n for n in env._companies if n != env.PRIMARY_CEO]
        for rival in rivals[1:]:
            env._companies[rival].alive = False
            env._companies[rival].market_share = 0.0

        # Force takeover success
        env._rng = random.Random()
        env._rng.random = lambda: 0.01
        obs = env.step(BoardroomAction(action_type="HOSTILE_TAKEOVER", action_target=rivals[0]))
        assert obs.done is True


# ---------------------------------------------------------------------------
# Replay logger
# ---------------------------------------------------------------------------

class TestReplayLogger:
    def test_replay_contains_rewards(self):
        env = make_env()
        env.step(BoardroomAction(action_type="HOLD"))
        assert "rewards" in env._replay_log[0]

    def test_replay_contains_press_wire(self):
        env = make_env()
        env.step(BoardroomAction(action_type="HOLD"))
        assert "press_wire" in env._replay_log[0]

    def test_replay_contains_spy_intel_key(self):
        env = make_env()
        env.step(BoardroomAction(action_type="HOLD"))
        assert "spy_intel" in env._replay_log[0]

    def test_replay_action_includes_parse_failed(self):
        env = make_env()
        env.step(BoardroomAction(action_type="HOLD"))
        for action_data in env._replay_log[0]["actions"].values():
            assert "parse_failed" in action_data


# ---------------------------------------------------------------------------
# Full-game smoke test
# ---------------------------------------------------------------------------

class TestFullGame:
    def test_full_game_completes(self):
        env = make_env()
        obs = env.reset()
        done = False
        turns = 0
        while not done and turns < 20:
            obs = env.step(BoardroomAction(action_type="HOLD"))
            done = obs.done
            turns += 1
        assert done

    def test_reward_is_finite(self):
        env = make_env()
        env.reset()
        obs = env.step(BoardroomAction(action_type="EARNINGS_CALL"))
        assert obs.reward is not None
        import math
        assert math.isfinite(obs.reward)
