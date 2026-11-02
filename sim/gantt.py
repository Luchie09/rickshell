"""Merge and render CPU schedule segments."""

from sim.metrics import Segment


def merge_segments(segments: list[Segment]) -> list[Segment]:
    """Join consecutive contiguous segments with the same label."""
    merged: list[Segment] = []
    for label, start, end in segments:
        if (
            merged
            and merged[-1][0] == label
            and merged[-1][2] == start
        ):
            previous_label, previous_start, _ = merged[-1]
            merged[-1] = (previous_label, previous_start, end)
        else:
            merged.append((label, start, end))
    return merged


def render_gantt(segments: list[Segment]) -> str:
    """Render schedule cells and place each time at its boundary column."""
    if not segments:
        return "(empty schedule)"

    segments = merge_segments(segments)
    cell_widths: list[int] = []
    for label, start, _ in segments:
        # Reserve enough room for both the label and its starting time.
        cell_widths.append(max(len(label) + 3, len(str(start))))

    first_line_parts: list[str] = []
    positions: list[int] = []
    position = 0
    for (label, _, _), width in zip(segments, cell_widths):
        positions.append(position)
        first_line_parts.append("| " + label + " " * (width - len(label) - 2))
        position += width
    first_line_parts.append("|")
    first_line = "".join(first_line_parts)

    timeline = [" "] * (position + max(1, len(str(segments[-1][2]))))
    boundary_times = [segment[1] for segment in segments]
    boundary_times.append(segments[-1][2])
    for start_column, time in zip(positions + [position], boundary_times):
        text = str(time)
        timeline[start_column : start_column + len(text)] = text

    return first_line + "\n" + "".join(timeline).rstrip()
