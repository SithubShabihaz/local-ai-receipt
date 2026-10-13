"""Deterministic heuristic and regular expression parser for invoices and receipts.

Operates 100% offline with zero external dependencies, serving as a reliable
production fallback and benchmark engine.
"""

import re
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from dateutil import parser as date_parser

from .models import ExtractedData, ExpenseCategory


class RegexParser:
    """High-precision regex and rule-based invoice extractor."""

    # Common vendor signatures for high-confidence matching
    KNOWN_VENDORS = {
        "tiger cloud": ("Tiger Cloud (TimescaleDB)", ExpenseCategory.SOFTWARE_CLOUD),
        "tiger data": ("Tiger Data Inc.", ExpenseCategory.SOFTWARE_CLOUD),
        "aws": ("Amazon Web Services (AWS)", ExpenseCategory.SOFTWARE_CLOUD),
        "amazon web services": ("Amazon Web Services (AWS)", ExpenseCategory.SOFTWARE_CLOUD),
        "github": ("GitHub Inc.", ExpenseCategory.SOFTWARE_CLOUD),
        "figma": ("Figma Inc.", ExpenseCategory.SOFTWARE_CLOUD),
        "adobe": ("Adobe Systems", ExpenseCategory.SOFTWARE_CLOUD),
        "stripe": ("Stripe Inc.", ExpenseCategory.PAYMENT_BANKING_FEES),
        "paypal": ("PayPal Holdings", ExpenseCategory.PAYMENT_BANKING_FEES),
        "starbucks": ("Starbucks Coffee", ExpenseCategory.MEALS_ENTERTAINMENT),
        "home depot": ("The Home Depot", ExpenseCategory.OFFICE_SUPPLIES),
        "uber": ("Uber Technologies", ExpenseCategory.TRAVEL_TRANSPORT),
        "lyft": ("Lyft Inc.", ExpenseCategory.TRAVEL_TRANSPORT),
        "upwork": ("Upwork Global Inc.", ExpenseCategory.PROFESSIONAL_SERVICES),
        "fiverr": ("Fiverr International", ExpenseCategory.PROFESSIONAL_SERVICES),
        "google ads": ("Google LLC (Ads)", ExpenseCategory.ADVERTISING_MARKETING),
        "meta ads": ("Meta Platforms (Ads)", ExpenseCategory.ADVERTISING_MARKETING),
        "godaddy": ("GoDaddy Inc.", ExpenseCategory.ADVERTISING_MARKETING),
        "namecheap": ("Namecheap Inc.", ExpenseCategory.ADVERTISING_MARKETING),
    }

    # Keyword rules for categorization
    CATEGORY_KEYWORDS = [
        (ExpenseCategory.SOFTWARE_CLOUD, [
            "cloud", "hosting", "server", "database", "timescaledb", "saas",
            "subscription", "api", "compute", "storage", "github", "docker",
            "figma", "software", "license", "ai", "llm"
        ]),
        (ExpenseCategory.OFFICE_SUPPLIES, [
            "office", "desk", "chair", "paper", "pen", "hardware", "monitor",
            "keyboard", "depot", "staples", "ikea", "printer", "cables"
        ]),
        (ExpenseCategory.MEALS_ENTERTAINMENT, [
            "coffee", "cafe", "espresso", "latte", "restaurant", "lunch",
            "dinner", "breakfast", "meal", "diner", "bistro", "food", "starbucks"
        ]),
        (ExpenseCategory.TRAVEL_TRANSPORT, [
            "ride", "trip", "uber", "lyft", "flight", "airline", "hotel",
            "taxi", "train", "amtrak", "parking", "mileage", "rental"
        ]),
        (ExpenseCategory.PROFESSIONAL_SERVICES, [
            "contractor", "freelance", "consulting", "legal", "cpa", "accounting",
            "developer", "designer", "upwork", "fiverr", "attorney"
        ]),
        (ExpenseCategory.PAYMENT_BANKING_FEES, [
            "processing fee", "stripe fee", "merchant fee", "bank charge",
            "transaction fee", "wire fee", "interchange", "payout fee"
        ]),
        (ExpenseCategory.ADVERTISING_MARKETING, [
            "ads", "advertising", "marketing", "campaign", "impressions",
            "clicks", "promotion", "domain", "seo", "newsletter"
        ]),
        (ExpenseCategory.UTILITIES_INTERNET, [
            "internet", "broadband", "wifi", "cellular", "mobile", "electric",
            "utility", "telecom", "verizon", "att", "t-mobile"
        ]),
    ]

    def extract(self, text: str) -> ExtractedData:
        """Extract structured financial data from raw invoice or receipt text."""
        vendor = self._extract_vendor(text)
        transaction_date = self._extract_date(text)
        total_amount, currency = self._extract_total(text)
        tax_amount = self._extract_tax(text)
        category = self._categorize(text, vendor)
        line_items = self._extract_line_items(text)
        notes = self._extract_invoice_number(text)

        # Calculate confidence score based on matches
        score = 0.5
        if vendor != "Unknown Vendor":
            score += 0.15
        if total_amount > 0.0:
            score += 0.2
        if tax_amount >= 0.0:
            score += 0.05
        if category != ExpenseCategory.OTHER_MISC:
            score += 0.1
        score = min(score, 0.95)

        return ExtractedData(
            vendor=vendor,
            transaction_date=transaction_date,
            total_amount=total_amount,
            currency=currency,
            tax_amount=tax_amount,
            category=category,
            line_items=line_items,
            notes=notes,
            confidence_score=round(score, 2),
        )

    def _extract_vendor(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        header_text = "\n".join(lines[:5]).lower() if lines else ""

        # 1. Check known vendors in the header lines first
        for key, (vendor_name, _) in self.KNOWN_VENDORS.items():
            if re.search(rf"\b{re.escape(key)}\b", header_text):
                return vendor_name

        # 2. Look for explicit headers: "Vendor:", "Merchant:", "Billed From:", "From:"
        vendor_match = re.search(
            r"(?:vendor|merchant|billed\s+from|from|seller|store):\s*([^\n\r]+)",
            text,
            re.IGNORECASE
        )
        if vendor_match:
            candidate = vendor_match.group(1).strip()
            if candidate and len(candidate) < 60:
                return candidate

        # 3. Check known vendors in full text with word boundary
        for key, (vendor_name, _) in self.KNOWN_VENDORS.items():
            if re.search(rf"\b{re.escape(key)}\b", text.lower()):
                return vendor_name

        # 4. Fallback: inspect the first non-empty lines (often the store header)
        for line in lines[:3]:
            # Skip lines with date, receipt title or amounts
            if not re.search(r"\b(receipt|invoice|bill|statement|tax|order|date|\$|\d{2,})\b", line, re.I):
                if 2 < len(line) < 40:
                    return line

        return lines[0][:40] if lines else "Unknown Vendor"

    def _extract_date(self, text: str) -> datetime:
        # Regex patterns for common date formats
        patterns = [
            # ISO: 2026-10-15 or 2026/10/15
            r"\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\b",
            # US/EU: 10/15/2026 or 15/10/2026
            r"\b(\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})\b",
            # Month name: Oct 15, 2026 or 15 October 2026
            r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2})\b",
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+20\d{2})\b",
        ]

        # First try finding date labeled with "Date:"
        labeled_match = re.search(
            r"(?:date|issued|billed|transaction\s*date|dated):\s*([^\n\r,]+)",
            text,
            re.IGNORECASE
        )
        if labeled_match:
            date_str = labeled_match.group(1).strip()
            try:
                parsed = date_parser.parse(date_str, fuzzy=True)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except Exception:
                pass

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    parsed = date_parser.parse(match.group(1), fuzzy=True)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed
                except Exception:
                    continue

        # Default fallback to current time
        return datetime.now(timezone.utc)

    def _extract_total(self, text: str) -> Tuple[float, str]:
        currency = "USD"
        if "€" in text or "EUR" in text:
            currency = "EUR"
        elif "£" in text or "GBP" in text:
            currency = "GBP"
        elif "CAD" in text or "C$" in text:
            currency = "CAD"

        # Explicit labeled totals: "Total: $120.50", "Grand Total: 45.00", "Amount Due: $99"
        total_patterns = [
            r"(?:grand\s+total|total\s+amount|amount\s+due|total\s+paid|balance\s+due|total):\s*(?:[$€£]|USD|EUR|GBP|CAD)?\s*([0-9,]+\.[0-9]{2})",
            r"(?:total|amount):\s*(?:[$€£]|USD|EUR|GBP|CAD)?\s*([0-9,]+(?:\.[0-9]{2})?)",
        ]

        for pat in total_patterns:
            matches = list(re.finditer(pat, text, re.IGNORECASE))
            if matches:
                # The last match for total is usually the grand total
                last_match = matches[-1]
                val_str = last_match.group(1).replace(",", "")
                try:
                    val = float(val_str)
                    if val > 0:
                        return val, currency
                except ValueError:
                    pass

        # Fallback: find all monetary numbers like $XX.XX and pick the maximum sensible number
        money_matches = re.findall(r"[$€£]\s*([0-9,]+\.[0-9]{2})", text)
        if money_matches:
            amounts = []
            for m in money_matches:
                try:
                    amounts.append(float(m.replace(",", "")))
                except ValueError:
                    pass
            if amounts:
                return max(amounts), currency

        return 0.0, currency

    def _extract_tax(self, text: str) -> float:
        tax_patterns = [
            # Handles "Estimated Tax (WA 9.15%): $7.05", "Tax (8.625%): $1.28", "State Tax: $20.27"
            r"(?:tax|vat|gst|sales\s+tax|state\s+tax|estimated\s+tax)(?:\s*\([^)]*\))?:\s*(?:[$€£]|USD|EUR|GBP|CAD)?\s*([0-9,]+\.[0-9]{2})",
            r"(?:tax|vat)\s+amount:\s*(?:[$€£]|USD|EUR|GBP|CAD)?\s*([0-9,]+\.[0-9]{2})",
        ]
        for pat in tax_patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    pass
        return 0.0

    def _categorize(self, text: str, vendor: str) -> ExpenseCategory:
        vendor_lower = vendor.lower()

        # 1. Check known vendor directly first
        for key, (_, cat) in self.KNOWN_VENDORS.items():
            if key in vendor_lower:
                return cat

        # 2. Keyword frequency scoring
        combined = f"{vendor} {text}".lower()
        scores: dict[ExpenseCategory, int] = {}
        for cat, keywords in self.CATEGORY_KEYWORDS:
            score = 0
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", combined):
                    score += 1
            if score > 0:
                scores[cat] = score

        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        return ExpenseCategory.OTHER_MISC

    def _extract_line_items(self, text: str) -> List[str]:
        items = []
        for line in text.splitlines():
            line = line.strip()
            # Line item often has a description followed by a price, e.g. "Item name ... $12.00"
            if re.search(r"[$€£]\s*\d+\.\d{2}", line) and not re.search(r"\b(subtotal|total|tax|discount|balance|due)\b", line, re.I):
                clean = re.sub(r"\s+", " ", line)
                if 4 < len(clean) < 120:
                    items.append(clean)
        return items[:10]

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        match = re.search(
            r"(?:invoice\s*(?:#|no\.?|id|num)?|receipt\s*(?:#|no\.?)|order\s*(?:#|id)):\s*([A-Za-z0-9-_]+)",
            text,
            re.IGNORECASE
        )
        if match:
            return f"Invoice #{match.group(1).strip()}"
        return None
