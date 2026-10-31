def responses_stop_details(response: OpenAIResponse) -> StopDetails | None:
    """Extract refusal detail from a Responses API result.

    The Responses API has no category breakdown; refusal text comes from
    `ResponseOutputRefusal` parts and the content-filter signal from
    `incomplete_details.reason`.
    """
    refusals: list[str] = []
    for output in response.output:
        if isinstance(output, ResponseOutputMessage):
            for c in output.content:
                if isinstance(c, ResponseOutputRefusal) and c.refusal:
                    refusals.append(c.refusal)

    explanation = "\n".join(refusals) if refusals else None
    incomplete = response.incomplete_details
    is_content_filter = (
        incomplete is not None
        and getattr(incomplete, "reason", None) == "content_filter"
    )

    if not explanation and not is_content_filter:
        return None

    return StopDetails(
        type="content_filter" if is_content_filter else "refusal",
        explanation=explanation or ("Response incomplete: content_filter" if is_content_filter else None),
    )

