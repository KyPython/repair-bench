def _chat_message_assistant_from_openai_response(
    model: str, response: OpenAIResponse, tools: list[ToolInfo]
) -> tuple[ChatMessageAssistant, StopReason, Logprobs | None]:
    """
    Transform OpenAI `Response` into an Inspect `ChatMessageAssistant` and `StopReason`.

    It maps each `ResponseOutputItem` in `output` to a `Content` in the
    `content` field of the `ChatMessageAssistant`.

    It also keeps track of the OpenAI id's for each of the items in `.output`.
    The way we're doing it assumes that there won't be multiple items of the
    same type in the output. This seems ok, but who knows.
    """
    # determine the StopReason
    stop_reason: StopReason
    match response.incomplete_details:
        case IncompleteDetails(reason="max_output_tokens"):
            stop_reason = "max_tokens"
        case IncompleteDetails(reason="content_filter"):
            stop_reason = "content_filter"
        case _:
            stop_reason = "stop"

    # process output items
    message_content, tool_calls, logprobs, has_tool_calls = (
        _process_response_output_items(response.output, tools)
    )

    if has_tool_calls and response.incomplete_details is None:
        stop_reason = "tool_calls"

    return (
        ChatMessageAssistant(
            content=message_content,
            tool_calls=tool_calls if len(tool_calls) > 0 else None,
            model=model,
            source="generate",
        ),
        stop_reason,
        logprobs,
    )

