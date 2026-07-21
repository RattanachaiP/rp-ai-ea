from brain.entry_location_intelligence import EntryLocationInput, EntryLocationIntelligence, EntryState


def data(**changes):
    base = dict(direction="BUY", current_price=4010.0, swing_high=4100.0, swing_low=4000.0, atr=10.0,
                recent_impulse_start=4000.0, recent_impulse_end=4010.0, pullback_detected=True,
                pullback_confirmed=True, structure_confirmed=True, liquidity_sweep_up=False,
                liquidity_sweep_down=False, nearest_support=4005.0, nearest_resistance=4050.0,
                expected_target=4040.0, invalidation_price=4000.0, execution_confidence=80.0)
    base.update(changes)
    return EntryLocationInput(**base)


def assess(**changes): return EntryLocationIntelligence().assess(data(**changes))


def test_buy_swing_high_and_sell_swing_low_are_hard_blocked():
    assert assess(current_price=4090, expected_target=4120).entry_state is EntryState.BLOCK_SWING_EXTREME
    assert assess(direction="SELL", current_price=4010, expected_target=3980, invalidation_price=4020).entry_state is EntryState.BLOCK_SWING_EXTREME


def test_confirmed_buy_low_and_sell_high_are_allowed():
    assert assess().entry_permission
    assert assess(direction="SELL", current_price=4090, recent_impulse_start=4100, recent_impulse_end=4090, expected_target=4060, invalidation_price=4100, nearest_support=4050, nearest_resistance=4095).entry_permission


def test_excessive_directional_extension_blocks_both_directions():
    assert assess(recent_impulse_end=4026, current_price=4026, expected_target=4060, pullback_confirmed=False).entry_state is EntryState.BLOCK_ATR_EXTENSION
    assert assess(direction="SELL", current_price=4074, recent_impulse_start=4100, recent_impulse_end=4074, expected_target=4040, invalidation_price=4084, pullback_confirmed=False).entry_state is EntryState.BLOCK_ATR_EXTENSION


def test_extended_move_without_pullback_waits_and_confirmation_improves_permission():
    waiting = assess(recent_impulse_end=4021, current_price=4021, expected_target=4050, pullback_detected=False, pullback_confirmed=False)
    assert waiting.entry_state is EntryState.WAIT_PULLBACK
    allowed = assess(recent_impulse_end=4021, current_price=4021, expected_target=4050)
    assert allowed.entry_permission and allowed.location_score > waiting.location_score


def test_poor_rr_and_invalid_geometry_fail_safely():
    assert assess(expected_target=4011).entry_state is EntryState.BLOCK_POOR_RR
    assert assess(swing_high=4000).entry_state is EntryState.BLOCK_INVALID_GEOMETRY
    assert assess(atr=0).entry_state is EntryState.BLOCK_INVALID_GEOMETRY
    assert assess(expected_target=3990).entry_state is EntryState.BLOCK_INVALID_GEOMETRY


def test_confidence_cannot_override_hard_block_or_invalid_target_geometry():
    assert not assess(current_price=4095, execution_confidence=100).entry_permission
    assert not assess(invalidation_price=4015, execution_confidence=100).entry_permission


def test_liquidity_sweep_requires_continuation_confirmation():
    result = assess(liquidity_sweep_up=True, pullback_confirmed=False)
    assert result.entry_state is EntryState.WAIT_CONFIRMATION
    assert assess(liquidity_sweep_up=True).entry_permission


def test_buy_sell_symmetry_and_determinism():
    buy = assess(current_price=4020, recent_impulse_end=4020, expected_target=4050)
    sell = assess(direction="SELL", current_price=4080, recent_impulse_start=4100, recent_impulse_end=4080, expected_target=4050, invalidation_price=4090, nearest_support=4050, nearest_resistance=4085)
    assert buy.entry_permission == sell.entry_permission
    assert buy.entry_state is sell.entry_state is EntryState.ENTRY_ALLOWED
    assert assess(current_price=4020, recent_impulse_end=4020, expected_target=4050) == buy
