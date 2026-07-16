"""Cliente de Google Sheets (vía gspread + cuenta de servicio).

Responsabilidad única: autenticarse y escribir filas en una hoja.
No conoce Business ni Supabase: recibe listas de valores y las escribe.

La API de Sheets permite ~60 escrituras/minuto: cada operación tiene
reintentos con esperas largas para absorber los 429.
"""

import gspread

from app.config.settings import GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SHEETS_ID
from app.utils.helpers import ensure_google_credentials
from app.utils.logger import logger
from app.utils.retry import retry

# Filas por petición: por debajo del límite de payload de la API
CHUNK_ROWS = 2000

# Reintentos para rate limit: espera 25s, 50s (la cuota es por minuto)
RATE_RETRY = dict(times=3, delay=25, backoff=2, exceptions=(gspread.exceptions.APIError,))


class SheetsClient:
    """Escritura de datos en el Google Sheet del proyecto."""

    def __init__(
        self,
        spreadsheet_id: str | None = None,
        service_account_file: str | None = None,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id or GOOGLE_SHEETS_ID
        self.service_account_file = (
            service_account_file or GOOGLE_SERVICE_ACCOUNT_FILE
        )
        if not self.spreadsheet_id:
            raise EnvironmentError("Falta GOOGLE_SHEETS_ID en el archivo .env")

        ensure_google_credentials()
        self._gc = gspread.service_account(filename=self.service_account_file)
        self._spreadsheet = self._gc.open_by_key(self.spreadsheet_id)

    def write_table(
        self,
        worksheet_name: str,
        header: list[str],
        rows: list[list],
    ) -> None:
        """Reemplaza el contenido de la pestaña con header + rows.

        Crea la pestaña si no existe. Escribe en bloques de CHUNK_ROWS.
        """
        worksheet = self._get_or_create_worksheet(
            worksheet_name, rows=len(rows) + 10, cols=len(header) + 2
        )
        self._clear(worksheet)

        all_rows = [header] + rows
        start = 0
        while start < len(all_rows):
            chunk = all_rows[start : start + CHUNK_ROWS]
            self._write_chunk(worksheet, chunk, start_row=start + 1)
            start += CHUNK_ROWS

        self._apply_format(worksheet)
        logger.info(
            f"Sheets: pestaña '{worksheet_name}' actualizada con "
            f"{len(rows)} filas"
        )

    # ------------------------------------------------------------------
    # Operaciones con reintentos (rate limit: 60 escrituras/minuto)
    # ------------------------------------------------------------------

    @retry(**RATE_RETRY)
    def _clear(self, worksheet) -> None:
        worksheet.clear()

    @retry(**RATE_RETRY)
    def _write_chunk(self, worksheet, chunk: list[list], start_row: int) -> None:
        worksheet.update(chunk, f"A{start_row}", value_input_option="RAW")

    @retry(**RATE_RETRY)
    def _apply_format(self, worksheet) -> None:
        """Header fijo y en negritas + texto recortado, en UNA sola llamada."""
        self._spreadsheet.batch_update(
            {
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": worksheet.id,
                                "gridProperties": {"frozenRowCount": 1},
                            },
                            "fields": "gridProperties.frozenRowCount",
                        }
                    },
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": worksheet.id,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True}
                                }
                            },
                            "fields": "userEnteredFormat.textFormat.bold",
                        }
                    },
                    {
                        "repeatCell": {
                            "range": {"sheetId": worksheet.id},
                            "cell": {
                                "userEnteredFormat": {"wrapStrategy": "CLIP"}
                            },
                            "fields": "userEnteredFormat.wrapStrategy",
                        }
                    },
                ]
            }
        )

    @retry(**RATE_RETRY)
    def _get_or_create_worksheet(self, name: str, rows: int, cols: int):
        try:
            worksheet = self._spreadsheet.worksheet(name)
            if worksheet.row_count < rows:
                worksheet.resize(rows=rows)
            return worksheet
        except gspread.WorksheetNotFound:
            logger.info(f"Sheets: creando pestaña '{name}'")
            return self._spreadsheet.add_worksheet(name, rows=rows, cols=cols)
