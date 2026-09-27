import pymupdf
import unicodedata
from storage.s3_asset_store import S3AssetStore
from storage.s3_table_store import S3TableStore
from processors.base_processor import BaseProcessor
from config.config import canonical_document_bucket
from models.document import ClinicalDocument, DocumentImage, DocumentPage, DocumentTable

class PDFProcessor(BaseProcessor):

    def __init__(
        self,
        ocr_processor=None,
        asset_store=None,
        table_store=None,
        pages_to_read="all",
        min_words_per_page: int = 20,
        min_quality_score: float = 0.6,
    ):
        super().__init__()

        self.ocr_processor = ocr_processor
        self.pages_to_read = pages_to_read
        self.min_words_per_page = min_words_per_page
        
        self.min_quality_score = min_quality_score
        

        self.asset_store = asset_store or S3AssetStore(canonical_document_bucket)

        self.table_store = table_store or S3TableStore(canonical_document_bucket)

    def _get_page_limit(
        self,
        total_pages: int,
    ) -> int:
        """
        Return the number of PDF pages to process.
        """

        if (
            isinstance(
                self.pages_to_read,
                str,
            )
            and self.pages_to_read.lower()
            == "all"
        ):
            return total_pages

        requested_pages = int(
            self.pages_to_read
        )

        if requested_pages < 1:
            raise ValueError(
                "pages_to_read must be 'all' "
                "or a positive integer."
            )

        return min(
            requested_pages,
            total_pages,
        )

    def _page_to_bytes(
        self,
        page,
    ) -> bytes:
        """
        Render a PDF page as PNG bytes for OCR.
        """

        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(
                2,
                2,
            )
        )

        return pixmap.tobytes("png")

    def _extract_images(
        self,
        page,
        page_number: int,
        document: ClinicalDocument,
    ) -> list[DocumentImage]:
        """
        Extract and upload meaningful images from one page.
        """

        images = []

        for image_index, image in enumerate(
            page.get_images(full=True)
        ):
            try:
                xref = image[0]

                image_details = (
                    page.parent.extract_image(
                        xref
                    )
                )

                width = image_details.get(
                    "width",
                    0,
                )

                height = image_details.get(
                    "height",
                    0,
                )

                if width < 50 or height < 50:
                    continue

                image_bytes = image_details[
                    "image"
                ]

                image_extension = (
                    image_details.get(
                        "ext",
                        "png",
                    )
                )

                image_id = (
                    f"image-{page_number}-"
                    f"{image_index + 1}"
                )

                image_key = (
                    self.asset_store.save_image(
                        document=document,
                        image_id=image_id,
                        image_bytes=image_bytes,
                        extension=(
                            image_extension
                        ),
                    )
                )

                images.append(
                    DocumentImage(
                        image_id=image_id,
                        page_number=page_number,
                        extension=(
                            image_extension
                        ),
                        s3_key=image_key,
                        width=width,
                        height=height,
                    )
                )

            except Exception:
                self.logger.exception(
                    f"Failed to extract image "
                    f"from page {page_number}."
                )

                document.warnings.append(
                    f"One image could not be extracted "
                    f"from page {page_number}."
                )

        return images

    def _extract_tables(
        self,
        page,
        page_number: int,
        document: ClinicalDocument,
    ) -> list[DocumentTable]:
        """
        Extract and upload tables from one page.
        """

        tables = []

        try:
            finder = page.find_tables()

        except Exception:
            self.logger.exception(
                f"Failed to discover tables "
                f"on page {page_number}."
            )

            document.warnings.append(
                f"Table discovery failed for "
                f"page {page_number}."
            )

            return tables

        for table_index, table in enumerate(finder.tables):
            try:
                rows = table.extract()

                table_id = (
                    f"table-{page_number}-"
                    f"{table_index + 1}"
                )

                row_count = len(rows)

                column_count = max((len(row) for row in rows ), default=0 )

                table_key = (
                    self.table_store.save_table(
                        document=document,
                        table_id=table_id,
                        rows=rows,
                    )
                )

                tables.append(
                    DocumentTable(
                        table_id=table_id,
                        page_number=page_number,
                        s3_key=table_key,
                        row_count=row_count,
                        column_count=column_count
                    ),
                )
                

            except Exception:
                self.logger.exception(
                    f"Failed to extract "
                    f"table {table_index + 1} "
                    f"from page {page_number}."
                )

                document.warnings.append(
                    f"Table {table_index + 1} "
                    f"could not be extracted "
                    f"from page {page_number}."
                )

        return tables

    def _cleanup_images(
        self,
        image_keys: list[str],
    ) -> None:
        """
        Delete images uploaded before a fatal failure.
        """

        for key in image_keys:
            try:
                self.asset_store.delete_image(
                    key
                )

                self.logger.info(
                    f"Deleted orphaned image: "
                    f"{key}"
                )

            except Exception:
                self.logger.exception(
                    f"Failed to delete orphaned "
                    f"image: {key}"
                )

    def _cleanup_tables(
        self,
        table_keys: list[str],
    ) -> None:
        """
        Delete tables uploaded before a fatal failure.
        """

        for key in table_keys:
            try:
                self.table_store.delete_table(
                    key
                )

                self.logger.info(
                    f"Deleted orphaned table: "
                    f"{key}"
                )

            except Exception:
                self.logger.exception(
                    f"Failed to delete orphaned "
                    f"table: {key}"
                )

    def _cleanup_uploaded_assets(
        self,
        image_keys: list[str],
        table_keys: list[str],
    ) -> None:
        """
        Roll back assets uploaded during a failed run.
        """

        self._cleanup_images(
            image_keys
        )

        self._cleanup_tables(
            table_keys
        )

    def quality_score(
        self,
        text: str,
    ) -> float:
        """
        Return the ratio of alphanumeric characters
        to all characters in the supplied text.
        """

        if not text.strip():
            return 0.0

        alphanumeric_count = sum(
            character.isalpha()
            or character.isdigit()
            for character in text
        )

        return (
            alphanumeric_count
            / len(text)
        )

    def requires_ocr(
        self,
        text: str,
    ) -> bool:
        """
        Determine whether extracted page text needs OCR.
        """

        word_count = len(
            text.split()
        )

        score = self.quality_score(
            text
        )

        low_quality = (
            score
            < self.min_quality_score
        )

        low_density = (
            word_count
            <= self.min_words_per_page
        )

        return (
            low_density
            or low_quality
        )

    def process(
        self,
        document: ClinicalDocument,
    ) -> ClinicalDocument:
        """
        Extract text, images, and tables from a PDF.
        """

        self.logger.info(
            f"Processing PDF: "
            f"{document.file_name}"
        )

        uploaded_image_keys = []
        uploaded_table_keys = []

        try:
            with pymupdf.open(
                document.local_file_path
            ) as pdf:

                pages = []
                images = []
                tables = []
                raw_text_parts = []

                current_offset = 0

                page_limit = (
                    self._get_page_limit(
                        len(pdf)
                    )
                )

                for page_index, page in enumerate(
                    pdf
                ):
                    if page_index >= page_limit:
                        break

                    page_number = (
                        page_index + 1
                    )

                    page_images = (
                        self._extract_images(
                            page=page,
                            page_number=(
                                page_number
                            ),
                            document=document,
                        )
                    )

                    images.extend(
                        page_images
                    )

                    uploaded_image_keys.extend(
                        image.s3_key
                        for image in page_images
                    )

                    page_tables = (
                        self._extract_tables(
                            page=page,
                            page_number=page_number,
                            document=document,
                        )
                    )

                    tables.extend(page_tables)

                    uploaded_table_keys.extend(table.s3_key for table in page_tables)

                    native_text = page.get_text()

                    native_text = unicodedata.normalize("NFKC", native_text)
                    page_text = native_text

                    word_count = len(page_text.split())

                    page_quality_score = self.quality_score(page_text)
                    
                    page_requires_ocr = self.requires_ocr(page_text)
                
                    extraction_method = "TEXT"

                    if (
                        page_requires_ocr
                        and self.ocr_processor
                    ):
                        self.logger.warning(
                            f"Page {page_number} "
                            f"flagged for OCR. "
                            f"Words={word_count}, "
                            f"Quality="
                            f"{page_quality_score:.2f}"
                        )

                        try:
                            image_bytes = self._page_to_bytes(page)
                            page_text = self.ocr_processor.extract_text(image_bytes)
                            page_text = unicodedata.normalize("NFKC", page_text)
                            
                            if not page_text.strip():
                                raise ValueError(f"OCR returned no text for page {page_number}.")

                            extraction_method = "OCR"

                            self.logger.info(
                                f"OCR completed for "
                                f"page {page_number}."
                            )

                        except Exception:
                            self.logger.exception(
                                f"OCR failed for "
                                f"page {page_number}. "
                                f"Using native text."
                            )
                            document.warnings.append(
                                f"OCR failed for page "
                                f"{page_number}; native text "
                                f"was retained."
                            )

                            page_text = native_text
                            extraction_method = (
                                "TEXT"
                            )

                    elif page_requires_ocr:
                        self.logger.warning(
                            f"Page {page_number} "
                            f"requires OCR, but no "
                            f"OCR processor is "
                            f"configured."
                        )

                        document.warnings.append(
                            f"Page {page_number} required OCR, "
                            f"but no OCR processor was configured."
                        )

                    word_count = len(
                        page_text.split()
                    )

                    page_quality_score = (
                        self.quality_score(
                            page_text
                        )
                    )

                    start_offset = (
                        current_offset
                    )

                    end_offset = (
                        start_offset
                        + len(page_text)
                    )

                    pages.append(
                        DocumentPage(
                            page_number=(
                                page_number
                            ),
                            text=page_text,
                            start_offset=(
                                start_offset
                            ),
                            end_offset=(
                                end_offset
                            ),
                            word_count=(
                                word_count
                            ),
                            quality_score=(
                                page_quality_score
                            ),
                            requires_ocr=(
                                page_requires_ocr
                            ),
                            ocr_applied=(
                                extraction_method
                                == "OCR"
                            ),
                            extraction_method=(
                                extraction_method
                            ),
                        )
                    )

                    raw_text_parts.append(
                        page_text
                    )

                    current_offset = (
                        end_offset + 1
                    )

                document.pages = pages
                document.images = images
                document.tables = tables

                document.page_count = len(
                    pages
                )

                document.ocr_page_count = sum(
                    1
                    for document_page in pages
                    if document_page.ocr_applied
                )

                document.image_count = len(
                    images
                )

                document.table_count = len(
                    tables
                )

                document.raw_text = "\n".join(
                    raw_text_parts
                )

                document.processing_status = (
                    "SUCCESS"
                )

                document.error_message = None

                self.logger.info(
                    f"PDF extraction completed. "
                    f"Pages="
                    f"{document.page_count}, "
                    f"Images="
                    f"{document.image_count}, "
                    f"Tables="
                    f"{document.table_count}, "
                    f"OCR Pages="
                    f"{document.ocr_page_count}, "
                    f"Warnings="
                    f"{len(document.warnings)}"
                )


            return document

        except Exception as exception:
            self.logger.exception(
                "PDF extraction failed."
            )

            self._cleanup_uploaded_assets(
                image_keys=(
                    uploaded_image_keys
                ),
                table_keys=(
                    uploaded_table_keys
                ),
            )

            document.raw_text = ""
            document.pages = []
            document.images = []
            document.tables = []

            document.page_count = 0
            document.ocr_page_count = 0
            document.image_count = 0
            document.table_count = 0

            document.processing_status = (
                "FAILED"
            )

            document.error_message = str(
                exception
            )

            return document
