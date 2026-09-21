from FFMpeG import (
    download_virtual,
    download_voice,
    parse_duration_range,
    get_media_duration,
    trim_voice
)


def get_virtual(url):
    return download_virtual(url)


def get_voice(url):
    return download_voice(url)


def get_voice_edit_range(value):
    return parse_duration_range(
        value
    )


def get_voice_duration(
    file_path
):
    return get_media_duration(
        file_path
    )


def edit_voice(
    source_file,
    start,
    end,
    output_file
):
    return trim_voice(
        source_file,
        start,
        end,
        output_file
    )
