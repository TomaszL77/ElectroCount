"""Conservative annotation roles, never a whitelist of device codes."""
import re


class TextRoleClassifier:
    def classify(self, text):
        text = ' '.join(text.upper().split())
        if text.rstrip(':') in ('LEGENDA', 'LEGEND', 'UWAGI', 'NOTES', 'OPIS', 'SYMBOL'):
            return 'DESCRIPTION', .99
        from .electrical_profile import modifier
        if modifier(text):return 'DEVICE_MODIFIER', .95
        if re.fullmatch(r'(?:W|O):[^\s]+', text):
            return 'CIRCUIT_REFERENCE', .97
        if re.fullmatch(r'[^\s/]+/\d+(?:[.\-]\d+)*', text):
            return 'CIRCUIT_REFERENCE', .97
        if re.fullmatch(r'(?:IP\s*\d{2}|EX|IK\d{2})', text):
            return 'DEVICE_MODIFIER', .95
        if re.fullmatch(r'(?:H\s*=\s*)?\d+(?:[.,]\d+)?\s*(?:W|KW|V|KV|MA|HZ|MM|MM2|M2|M)', text):
            return 'DESCRIPTION', .98
        if text.startswith(('ROZDZIELNICA ', 'TABLICA ')):
            return 'DESCRIPTION', .9
        # A code may be numeric or arbitrary text. Space and length are weak
        # priors only; spatial evidence still has to select an unambiguous item.
        if not text or len(text) > 80:
            return 'UNKNOWN', .25
        return 'DEVICE_LABEL', .78 if text.isdigit() else (.65 if ' ' in text else .9)
