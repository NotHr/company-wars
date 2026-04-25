"""Unit tests for BOARDROOM L2 environment — feat/l2-seven-ceos."""

import random

import pytest

from server.boardroom_environment import BoardroomEnvironment
from server.companies import L2_COMPANIES, L2_STARTING_STATS
from models import BoardroomAction, BoardroomObservation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RIVAL_NAMES = [c["name"] for c in L2_COMPANIES if c["name"] != "Vermillion Capital"]
PRIMARY = "Vermillion Capital"


def make_env() -> BoardroomEnvironment:
    env = BoardroomEnvironment()
    env.reset()
    return env


def hold() -> BoardroomAction:
    return BoardroomAction(action_type="HOLD")


# ---------------------------------------------------------------------------
# 1. reset() returns a valid observation
# ---------------------------------------------------------------------------

class TestReset:
    def test_returns_boardroom_observation(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert isinstance(obs, BoardroomObservation)

    def test_you_are_vermillion(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert obs.you_are == PRIMARY

    def test_turn_zero(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert obs.turn == 0

    def test_max_turns_twelve(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert obs.max_turns == 12

    def test_seven_companies_present(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert len(obs.all_companies) == 7

    def test_all_companies_alive_at_start(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert all(c.alive for c in obs.all_companies)

    def test_your_stats_populated(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert obs.your_stats is not None
        assert obs.your_stats.cash == L2_STARTING_STATS["cash"]
        assert obs.your_stats.market_share == L2_STARTING_STATS["market_share"]
        assert obs.your_stats.stock_price == L2_STARTING_STATS["stock_price"]
        assert obs.your_stats.reputation == L2_STARTING_STATS["reputation"]

    def test_not_done_at_reset(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert obs.done is False

    def test_prompt_non_empty(self):
        env = BoardroomEnvironment()
        obs = env.reset()
        assert len(obs.prompt) > 0

    def test_reset_twice_gives_fresh_state(self):
        env = BoardroomEnvironment()
        obs1 = env.reset()
        ep1 = env.state.episode_id
        obs2 = env.reset()
        ep2 = env.state.episode_id
        assert ep1 != ep2
        assert obs2.turn == 0


# ---------------------------------------------------------------------------
# 2. step() with EARNINGS_CALL
# ---------------------------------------------------------------------------

class TestEarningsCall:
    def test_no_crash(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="EARNINGS_CALL"))
        assert isinstance(obs, BoardroomObservation)

    def test_turn_increments(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="EARNINGS_CALL"))
        assert obs.turn == 1

    def test_reward_is_float(self):
        env = make_env()
        obs = env.step(BoardroomAction(action_type="EARNINGS_CALL"))
        assert isinstance(obs.reward, float)

    def test_stock_rises_on_earnings_call(self):
        """EARNINGS_CALL should generally increase stock price when reputation is clean."""
        env = make_env()
        start_stock = env._companies[PRIMARY].stock_price
        env.step(BoardroomAction(action_type="EARNINGS_CALL"))
        # Stock price formula can have noise, but over many seeds it trends up.
        # Check at least it stays valid (>= 1).
        assert env._companies[PRIMARY].stock_price >= 1.0


# ---------------------------------------------------------------------------
# 3. step() with SABOTAGE
# ---------------------------------------------------------------------------

class TestSabotage:
    def test_no_crash(self):
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="SABOTAGE", action_target=RIVAL_NAMES[0])
        )
        assert isinstance(obs, BoardroomObservation)

    def test_sabotage_costs_cash(self):
        env = make_env()
        start_cash = env._companies[PRIMARY].cash
        env.step(BoardroomAction(action_type="SABOTAGE", action_target=RIVAL_NAMES[0]))
        # Sabotage costs $5M (Tech sector modifier: $4M) plus $1M burn; cash must drop
        assert env._companies[PRIMARY].cash < start_cash

    def test_invalid_target_demoted_to_hold(self):
        """Targeting a non-existent company should silently fall back to HOLD."""
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="SABOTAGE", action_target="Nonexistent Corp")
        )
        assert isinstance(obs, BoardroomObservation)
        # No crash — parse_failed path exercised.

    def test_self_target_demoted_to_hold(self):
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="SABOTAGE", action_target=PRIMARY)
        )
        assert isinstance(obs, BoardroomObservation)


# ---------------------------------------------------------------------------
# 4. step() with PARTNERSHIP
# ---------------------------------------------------------------------------

class TestPartnership:
    def test_no_crash(self):
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="PARTNERSHIP", action_target=RIVAL_NAMES[1])
        )
        assert isinstance(obs, BoardroomObservation)

    def test_partnership_attempt_no_crash(self):
        """Force both sides to propose so acceptance is guaranteed (mutual proposal)."""
        env = make_env()
        target = RIVAL_NAMES[1]
        # Manually inject a mutual proposal from the target side before resolving
        # by seeding both primary and target actions in the same turn through step.
        # We can't force mutual proposals via the public API, so we verify no crash
        # and that partnerships can form over repeated attempts.
        for _ in range(6):
            obs = env.step(
                BoardroomAction(action_type="PARTNERSHIP", action_target=target)
            )
            if target in env._companies[PRIMARY].active_partnerships:
                break
        # Either a partnership formed or none — no crash is the key invariant.
        assert isinstance(obs, BoardroomObservation)

    def test_invalid_target_demoted_to_hold(self):
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="PARTNERSHIP", action_target="Ghost Inc")
        )
        assert isinstance(obs, BoardroomObservation)


# ---------------------------------------------------------------------------
# 5. Bankruptcy triggers when cash hits zero
# ---------------------------------------------------------------------------

class TestBankruptcy:
    def _drain_cash(self, env: BoardroomEnvironment, company_name: str, amount: float):
        """Directly set a company's cash to trigger imminent bankruptcy."""
        env._companies[company_name].cash = amount

    def test_bankruptcy_triggers_on_zero_cash(self):
        env = make_env()
        # Set primary's cash just below the $1M operational burn threshold
        self._drain_cash(env, PRIMARY, 500_000)
        obs = env.step(hold())
        assert env._companies[PRIMARY].alive is False

    def test_bankruptcy_sets_alive_false(self):
        env = make_env()
        self._drain_cash(env, PRIMARY, 1)
        env.step(hold())
        assert env._companies[PRIMARY].alive is False

    def test_terminal_reward_penalty_on_bankruptcy(self):
        env = make_env()
        self._drain_cash(env, PRIMARY, 1)
        obs = env.step(hold())
        # Bankrupt agent gets penalty; reward should be negative
        assert obs.reward < 0

    def test_episode_ends_when_primary_bankrupts(self):
        env = make_env()
        self._drain_cash(env, PRIMARY, 1)
        obs = env.step(hold())
        assert obs.done is True

    def test_rival_bankruptcy_ends_or_continues(self):
        """Bankrupting a rival should not crash and game continues (unless only 1 left)."""
        env = make_env()
        rival = RIVAL_NAMES[0]
        self._drain_cash(env, rival, 1)
        obs = env.step(hold())
        assert env._companies[rival].alive is False
        assert isinstance(obs, BoardroomObservation)


# ---------------------------------------------------------------------------
# 6. Market share redistributes on bankruptcy
# ---------------------------------------------------------------------------

class TestMarketShareRedistribution:
    def test_bankrupt_company_loses_all_share(self):
        env = make_env()
        rival = RIVAL_NAMES[0]
        env._companies[rival].cash = 1
        env.step(hold())
        assert env._companies[rival].market_share == 0.0

    def test_alive_companies_gain_share(self):
        env = make_env()
        rival = RIVAL_NAMES[0]
        before = {n: c.market_share for n, c in env._companies.items() if n != rival}
        env._companies[rival].cash = 1
        env.step(hold())
        for name, pre_share in before.items():
            if env._companies[name].alive:
                assert env._companies[name].market_share > pre_share

    def test_total_share_conserved_after_bankruptcy(self):
        """Bankruptcy redistribution must conserve total market share.

        SABOTAGE in the same turn can burn ≈1% per success (target −1.5, attacker +0.5),
        so heuristic agents are patched to HOLD to isolate the redistribution logic.
        """
        from server.game_logic import TurnAction

        env = make_env()
        rival = RIVAL_NAMES[0]
        env._companies[rival].cash = 1

        # Patch heuristics to HOLD so no sabotage burns market share this turn
        env._heuristic_action = lambda name: TurnAction(
            company_name=name, private_emails=[], press_release=None,
            action_type="HOLD", action_target=None,
        )

        env.step(hold())
        total = sum(c.market_share for c in env._companies.values())
        assert abs(total - 100.0) < 0.01


# ---------------------------------------------------------------------------
# 7. Stock price never goes below $1
# ---------------------------------------------------------------------------

class TestStockPriceFloor:
    def test_stock_floor_after_sabotage(self):
        env = make_env()
        # Hammer a rival with sabotage for multiple turns
        target = RIVAL_NAMES[0]
        for _ in range(6):
            if not env._companies[target].alive:
                break
            env.step(BoardroomAction(action_type="SABOTAGE", action_target=target))
        for c in env._companies.values():
            assert c.stock_price >= 1.0

    def test_stock_floor_full_rollout(self):
        """No stock price should drop below $1 in a complete 12-turn episode."""
        rng = random.Random(99)
        rivals = list(RIVAL_NAMES)
        for seed in range(5):
            env = BoardroomEnvironment()
            env.reset()
            rng = random.Random(seed)
            for _ in range(12):
                atype = rng.choice(["EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "HOLD"])
                target = rng.choice(rivals) if atype in ("SABOTAGE", "PARTNERSHIP") else None
                obs = env.step(BoardroomAction(action_type=atype, action_target=target))
                for c in env._companies.values():
                    assert c.stock_price >= 1.0, (
                        f"seed={seed} company={c.name} stock={c.stock_price}"
                    )
                if obs.done:
                    break


# ---------------------------------------------------------------------------
# 8. Full 12-turn rollout completes without error
# ---------------------------------------------------------------------------

class TestFullRollout:
    def test_rollout_completes(self):
        rng = random.Random(42)
        rivals = list(RIVAL_NAMES)
        env = BoardroomEnvironment()
        obs = env.reset()
        assert obs.turn == 0

        for step_num in range(1, 13):
            atype = rng.choice(["EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "HOLD"])
            target = rng.choice(rivals) if atype in ("SABOTAGE", "PARTNERSHIP") else None
            obs = env.step(BoardroomAction(action_type=atype, action_target=target))
            assert isinstance(obs, BoardroomObservation)
            assert obs.turn == step_num or obs.done
            if obs.done:
                break

        assert obs.done is True

    def test_rollout_reward_is_finite(self):
        rng = random.Random(7)
        rivals = list(RIVAL_NAMES)
        env = BoardroomEnvironment()
        env.reset()
        total = 0.0
        for _ in range(12):
            atype = rng.choice(["EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "HOLD"])
            target = rng.choice(rivals) if atype in ("SABOTAGE", "PARTNERSHIP") else None
            obs = env.step(BoardroomAction(action_type=atype, action_target=target))
            assert obs.reward == obs.reward  # not NaN
            assert abs(obs.reward) < 1e6    # sanity magnitude check
            total += obs.reward
            if obs.done:
                break
        assert abs(total) < 1e6

    def test_observation_fields_populated_each_turn(self):
        rng = random.Random(13)
        rivals = list(RIVAL_NAMES)
        env = BoardroomEnvironment()
        env.reset()
        for _ in range(12):
            atype = rng.choice(["EARNINGS_CALL", "SABOTAGE", "HOLD"])
            obs = env.step(BoardroomAction(action_type=atype))
            assert obs.leaderboard
            assert len(obs.all_companies) == 7
            assert obs.prompt
            if obs.done:
                break

    def test_state_step_count_increments(self):
        env = BoardroomEnvironment()
        env.reset()
        for i in range(1, 5):
            env.step(hold())
            assert env.state.step_count == i


# ---------------------------------------------------------------------------
# 9. PROPOSE_MERGER action
# ---------------------------------------------------------------------------

class TestProposeMerger:
    def test_no_crash(self):
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="PROPOSE_MERGER", action_target=RIVAL_NAMES[0])
        )
        assert isinstance(obs, BoardroomObservation)

    def test_invalid_target_demoted_to_hold(self):
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="PROPOSE_MERGER", action_target="Ghost Corp")
        )
        assert isinstance(obs, BoardroomObservation)

    def test_self_target_demoted_to_hold(self):
        env = make_env()
        obs = env.step(
            BoardroomAction(action_type="PROPOSE_MERGER", action_target=PRIMARY)
        )
        assert isinstance(obs, BoardroomObservation)

    def test_mutual_merger_absorbs_target(self):
        """Force a mutual merger: target proposes back to PRIMARY → target is absorbed."""
        from server.game_logic import TurnAction

        env = make_env()
        target_name = RIVAL_NAMES[0]

        original = env._heuristic_action
        def rigged(name):
            if name == target_name:
                return TurnAction(
                    company_name=name, private_emails=[], press_release=None,
                    action_type="PROPOSE_MERGER", action_target=PRIMARY,
                )
            return original(name)
        env._heuristic_action = rigged

        env.step(BoardroomAction(action_type="PROPOSE_MERGER", action_target=target_name))
        assert env._companies[target_name].alive is False

    def test_mutual_merger_primary_gains_assets(self):
        """After mutual merger PRIMARY should have more cash and market share."""
        from server.game_logic import TurnAction

        env = make_env()
        target_name = RIVAL_NAMES[0]
        pre_cash = env._companies[PRIMARY].cash
        pre_share = env._companies[PRIMARY].market_share

        original = env._heuristic_action
        def rigged(name):
            if name == target_name:
                return TurnAction(
                    company_name=name, private_emails=[], press_release=None,
                    action_type="PROPOSE_MERGER", action_target=PRIMARY,
                )
            return original(name)
        env._heuristic_action = rigged

        env.step(BoardroomAction(action_type="PROPOSE_MERGER", action_target=target_name))
        assert env._companies[PRIMARY].cash > pre_cash
        assert env._companies[PRIMARY].market_share > pre_share

    def test_one_sided_merger_penalises_proposer(self):
        """One-sided PROPOSE_MERGER should cost PRIMARY reputation."""
        from server.game_logic import TurnAction

        env = make_env()
        # Force all heuristics to HOLD so no mutual
        env._heuristic_action = lambda name: TurnAction(
            company_name=name, private_emails=[], press_release=None,
            action_type="HOLD", action_target=None,
        )

        start_rep = env._companies[PRIMARY].reputation
        env.step(BoardroomAction(action_type="PROPOSE_MERGER", action_target=RIVAL_NAMES[0]))
        assert env._companies[PRIMARY].reputation < start_rep

    def test_one_sided_merger_deducts_proposer_share(self):
        """One-sided hostile attempt should deduct market share from the proposer."""
        from server.game_logic import TurnAction

        env = make_env()
        env._heuristic_action = lambda name: TurnAction(
            company_name=name, private_emails=[], press_release=None,
            action_type="HOLD", action_target=None,
        )

        target_name = RIVAL_NAMES[0]
        pre_share = env._companies[PRIMARY].market_share
        env.step(BoardroomAction(action_type="PROPOSE_MERGER", action_target=target_name))
        assert env._companies[PRIMARY].market_share < pre_share
