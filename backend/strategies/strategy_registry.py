try:
    from .cover_strategy import CoverStrategy
    from .train_multi_clean_strategy import TrainMultiCleanStrategy
    from .train_single_long_strategy import TrainSingleLongStrategy
except ImportError:
    from strategies.cover_strategy import CoverStrategy
    from strategies.train_multi_clean_strategy import TrainMultiCleanStrategy
    from strategies.train_single_long_strategy import TrainSingleLongStrategy


_STRATEGIES = {
    CoverStrategy.strategy_key: CoverStrategy(),
    TrainSingleLongStrategy.strategy_key: TrainSingleLongStrategy(),
    TrainMultiCleanStrategy.strategy_key: TrainMultiCleanStrategy(),
}


def resolve_train_strategy(file_count: int, single_long_eligible: bool | None = None) -> str:
    if file_count > 1:
        return TrainMultiCleanStrategy.strategy_key
    if single_long_eligible is False:
        return TrainMultiCleanStrategy.strategy_key
    return TrainSingleLongStrategy.strategy_key


def get_strategy(strategy_key: str):
    if strategy_key not in _STRATEGIES:
        raise KeyError(f"未注册的 strategy_key: {strategy_key}")
    return _STRATEGIES[strategy_key]
