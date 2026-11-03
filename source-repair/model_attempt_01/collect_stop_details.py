def collect_stop_details(
    provider: str,
    logger: Logger,
    fn: Callable[[], StopDetails | None],
) -> StopDetails | None:
    """Defensively collect `StopDetails` from a provider response.

    Calls `fn()` (a provider-specific extractor), catching any unexpected data
    shape so a surprising payload warns rather than breaking generation. Also
    normalizes the result: drops empty details and keeps the scalar `category`
    in sync with `categories[0]`.

    Args:
        provider: Provider name (used in the warning message).
        logger: Logger to emit a one-time warning to on failure.
        fn: Extractor returning `StopDetails | None`.

    Returns:
        Normalized `StopDetails`, or `None` when there is nothing to report or
        an unexpected shape was encountered.
    """
    try:
        details = fn()
    except Exception as ex:
        warn_once(
            logger,
            f"Unexpected data shape collecting stop_details from {provider}: {ex}",
        )
        return None

    # only attach when there is something to report
    if details is None or (not details.categories and not details.explanation):
        return None

    # keep the high-level summary in sync with the canonical list
    if details.category is None and details.categories:
        details.category = details.categories[0].category
    if details.explanation is None and details.categories:
        details.explanation = _summarize_stop_categories(details.categories)

    return details

