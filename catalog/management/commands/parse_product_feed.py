from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from django.core.management.base import BaseCommand, CommandError, CommandParser

PREDEFINED_SUPPLIERS = [
    {'code': 'SUP_001', 'name': 'UbiPharm Guinée'},
    {'code': 'SUP_002', 'name': 'SODIPHARM'},
    {'code': 'SUP_003', 'name': 'SOGUIPREM'},
    {'code': 'SUP_004', 'name': 'Laborex Guinée'},
    {'code': 'SUP_005', 'name': 'PCG-LABE'},
    {'code': 'SUP_006', 'name': 'PHARMAGUI-ORIEN.SA'},
    {'code': 'SUP_007', 'name': 'Africa Health Care Pharma'},
]


@dataclass
class ParsedProduct:
    source_id: Optional[int]
    name: str
    barcode: str
    category_name: str
    dosage_form_name: str
    quantity: Optional[int]
    cost: Optional[Decimal]
    price: Optional[Decimal]
    stock_alert: Optional[int]
    expiration_date: Optional[str]
    note: Optional[str]
    supplier_name: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_id': self.source_id,
            'name': self.name,
            'barcode': self.barcode,
            'category_name': self.category_name,
            'dosage_form_name': self.dosage_form_name,
            'quantity': self.quantity,
            'cost': str(self.cost) if self.cost is not None else None,
            'price': str(self.price) if self.price is not None else None,
            'stock_alert': self.stock_alert,
            'expiration_date': self.expiration_date,
            'note': self.note,
            'supplier_name': self.supplier_name,
            'errors': self.errors,
        }


class Command(BaseCommand):
    help = "Parse a product feed JSON file and extract normalized data without importing it."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('input_file', type=str, help='Path to the JSON feed to parse.')
        parser.add_argument(
            '--output',
            type=str,
            help='Optional path to write the parsed output JSON. Prints to stdout if omitted.',
        )

    def handle(self, *args, **options) -> None:
        input_path = Path(options['input_file'])
        output_path = Path(options['output']) if options.get('output') else None

        if not input_path.exists():
            raise CommandError(f"Input file {input_path} does not exist.")

        with input_path.open('r', encoding='utf-8-sig') as stream:
            try:
                payload = json.load(stream)
            except json.JSONDecodeError as exc:
                raise CommandError(f'Failed to parse JSON file: {exc}') from exc

        products_raw = payload.get('data', [])
        barcode_error_counter = 1
        categories: Dict[str, Dict[str, str]] = {}
        dosage_forms: Dict[str, Dict[str, str]] = {}
        parsed_products: List[ParsedProduct] = []
        errors: List[Dict[str, Any]] = []

        for index, raw in enumerate(products_raw, start=1):
            product = self._parse_single_product(raw, barcode_error_counter)
            if product.barcode.startswith('BARCODEERROR'):
                barcode_error_counter += 1

            categories.setdefault(
                product.category_name.lower(),
                {'name': product.category_name, 'source_ids': []},
            )['source_ids'].append(product.source_id)

            dosage_forms.setdefault(
                product.dosage_form_name.lower(),
                {'name': product.dosage_form_name, 'source_ids': []},
            )['source_ids'].append(product.source_id)

            parsed_products.append(product)

            for error in product.errors:
                errors.append(
                    {
                        'source_id': product.source_id,
                        'index': index,
                        'issue': error,
                    }
                )

        output_payload = {
            'metadata': {
                'total_records': payload.get('recordsTotal'),
                'filtered_records': payload.get('recordsFiltered'),
            },
            'suppliers': PREDEFINED_SUPPLIERS,
            'categories': [
                {'name': item['name'], 'sources': item['source_ids']}
                for item in categories.values()
            ],
            'dosage_forms': [
                {'name': item['name'], 'sources': item['source_ids']}
                for item in dosage_forms.values()
            ],
            'products': [product.to_dict() for product in parsed_products],
            'errors': errors,
        }

        serialized = json.dumps(output_payload, indent=2, ensure_ascii=False)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(serialized, encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'Parsed data written to {output_path}'))
        else:
            self.stdout.write(serialized)

        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {len(parsed_products)} products. '
                f'{len(categories)} category candidates, {len(dosage_forms)} dosage forms.'
            )
        )

    def _parse_single_product(self, raw: Dict[str, Any], barcode_error_counter: int) -> ParsedProduct:
        errors: List[str] = []
        barcode = self._normalize_barcode(raw.get('product_code'), barcode_error_counter)
        if barcode.startswith('BARCODEERROR'):
            errors.append('Missing or invalid product_code; generated fallback identifier.')

        category_name = raw.get('product_barcode_symbology') or 'Catégorie inconnue'
        dosage_form_name = raw.get('category', {}).get('category_name') or 'Forme inconnue'
        note = raw.get('product_note')

        cost = self._parse_currency(raw.get('product_cost'), errors, field='product_cost')
        price = self._parse_currency(raw.get('product_price'), errors, field='product_price')
        quantity = self._parse_int(raw.get('product_quantity'), errors, field='product_quantity')
        stock_alert = self._parse_int(raw.get('product_stock_alert'), errors, field='product_stock_alert')

        expiration_date = raw.get('product_date_peremption')

        return ParsedProduct(
            source_id=raw.get('id'),
            name=raw.get('product_name') or '',
            barcode=barcode,
            category_name=category_name,
            dosage_form_name=dosage_form_name,
            quantity=quantity,
            cost=cost,
            price=price,
            stock_alert=stock_alert,
            expiration_date=expiration_date,
            note=note,
            errors=errors,
        )

    @staticmethod
    def _normalize_barcode(value: Optional[str], fallback_counter: int) -> str:
        if value and isinstance(value, str) and value.strip():
            return value.strip()
        return f'BARCODEERROR{fallback_counter}'

    @staticmethod
    def _parse_currency(value: Optional[str], errors: List[str], *, field: str) -> Optional[Decimal]:
        if value in (None, ''):
            return None
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        if isinstance(value, str):
            cleaned = re.sub(r'[^\d,.-]', '', value)
            cleaned = cleaned.replace(',', '').replace('.', '')
            if cleaned == '':
                errors.append(f'Unable to parse {field}: original value "{value}"')
                return None
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                errors.append(f'Unable to parse {field} as decimal: "{value}"')
                return None
        errors.append(f'Unexpected type for {field}: {type(value).__name__}')
        return None

    @staticmethod
    def _parse_int(value: Any, errors: List[str], *, field: str) -> Optional[int]:
        if value in (None, ''):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            cleaned = re.sub(r'[^\d-]', '', value)
            if cleaned == '':
                errors.append(f'Unable to parse {field}: original value "{value}"')
                return None
            try:
                return int(cleaned)
            except ValueError:
                errors.append(f'Unable to parse {field} as integer: "{value}"')
                return None
        errors.append(f'Unexpected type for {field}: {type(value).__name__}')
        return None

