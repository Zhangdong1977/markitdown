import sys
import io
from warnings import warn

from typing import BinaryIO, Any

from ._html_converter import HtmlConverter
from ..converter_utils.docx.pre_process import pre_process_docx
from .._base_converter import DocumentConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE

# Try loading optional (but in this case, required) dependencies
# Save reporting of any exceptions for later
_dependency_exc_info = None
try:
    import mammoth

except ImportError:
    # Preserve the error and stack trace for later
    _dependency_exc_info = sys.exc_info()


ACCEPTED_MIME_TYPE_PREFIXES = [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]

ACCEPTED_FILE_EXTENSIONS = [".docx"]


class DocxConverter(HtmlConverter):
    """
    Converts DOCX files to Markdown. Style information (e.g.m headings) and tables are preserved where possible.
    """

    def __init__(self):
        super().__init__()
        self._html_converter = HtmlConverter()

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
    ) -> DocumentConverterResult:
        # Check: the dependencies
        if _dependency_exc_info is not None:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".docx",
                    feature="docx",
                )
            ) from _dependency_exc_info[
                1
            ].with_traceback(  # type: ignore[union-attr]
                _dependency_exc_info[2]
            )

        style_map = kwargs.get("style_map", None)
        progress_callback = kwargs.get("progress_callback", None)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[MARKITDOWN-DOCX] About to call pre_process_docx")
        pre_process_stream = pre_process_docx(file_stream)
        logger.info(f"[MARKITDOWN-DOCX] pre_process_docx returned, stream position: {pre_process_stream.tell()}")

        # Build mammoth kwargs
        mammoth_kwargs = {"style_map": style_map} if style_map else {}
        if progress_callback:
            mammoth_kwargs["progress_callback"] = progress_callback

        logger.info(f"[MARKITDOWN-DOCX] About to call mammoth.convert_to_html, progress_callback={progress_callback is not None}")

        mammoth_result = mammoth.convert_to_html(pre_process_stream, **mammoth_kwargs)
        html_content = mammoth_result.value
        logger.info(f"[MARKITDOWN-DOCX] mammoth.convert_to_html returned, html length: {len(html_content)}")

        return self._html_converter.convert_string(
            html_content,
            **kwargs,
        )
