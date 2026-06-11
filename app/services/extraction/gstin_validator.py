"""
GSTIN validator with checksum verification
"""

from typing import Optional, Tuple
import structlog

logger = structlog.get_logger()


# State codes mapping
STATE_CODES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman and Diu (old)",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

# Entity type codes
ENTITY_CODES = {
    "P": "Proprietorship",
    "F": "Partnership Firm",
    "C": "Company",
    "H": "HUF (Hindu Undivided Family)",
    "A": "AOP (Association of Persons)",
    "T": "Trust",
    "B": "BOI (Body of Individuals)",
    "L": "Local Authority",
    "J": "Artificial Juridical Person",
    "G": "Government",
    "K": "Statutory Corporation",
    "N": "Not-for-profit",
    "U": "LLP (Limited Liability Partnership)",
    "D": "Division within Business",
    "E": "Others",
}


class GSTINValidator:
    """
    GSTIN validator with checksum verification

    GSTIN Format: SSPPPPPPPPPPEZC
    - SS: State code (2 digits)
    - PPPPPPPPPP: PAN (10 characters)
    - E: Entity code (1 character)
    - Z: Always 'Z' (default)
    - C: Checksum (1 character)
    """

    # Character values for checksum calculation
    CHAR_VALUES = {
        '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
        '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14,
        'F': 15, 'G': 16, 'H': 17, 'I': 18, 'J': 19,
        'K': 20, 'L': 21, 'M': 22, 'N': 23, 'O': 24,
        'P': 25, 'Q': 26, 'R': 27, 'S': 28, 'T': 29,
        'U': 30, 'V': 31, 'W': 32, 'X': 33, 'Y': 34,
        'Z': 35,
    }

    @classmethod
    def validate(cls, gstin: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GSTIN format and checksum

        Args:
            gstin: 15-character GSTIN

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not gstin:
            return False, "GSTIN is empty"

        gstin = gstin.upper().strip()

        # Check length
        if len(gstin) != 15:
            return False, f"Invalid length: {len(gstin)} (expected 15)"

        # Validate state code
        state_code = gstin[:2]
        if state_code not in STATE_CODES:
            return False, f"Invalid state code: {state_code}"

        # Validate PAN format (positions 2-11)
        pan = gstin[2:12]
        if not cls._validate_pan_format(pan):
            return False, f"Invalid PAN format: {pan}"

        # Validate entity code (position 12)
        entity_code = gstin[12]
        if entity_code not in ENTITY_CODES and not entity_code.isdigit():
            return False, f"Invalid entity code: {entity_code}"

        # Check 'Z' at position 13
        if gstin[13] != 'Z':
            return False, f"Position 14 must be 'Z', found: {gstin[13]}"

        # Validate checksum
        expected_checksum = cls._calculate_checksum(gstin[:14])
        actual_checksum = gstin[14]

        if expected_checksum != actual_checksum:
            return False, f"Invalid checksum: expected {expected_checksum}, found {actual_checksum}"

        return True, None

    @classmethod
    def _validate_pan_format(cls, pan: str) -> bool:
        """Validate PAN format: 5 letters + 4 digits + 1 letter"""
        if len(pan) != 10:
            return False

        # First 5 must be letters
        if not pan[:5].isalpha():
            return False

        # Next 4 must be digits
        if not pan[5:9].isdigit():
            return False

        # Last must be letter
        if not pan[9].isalpha():
            return False

        return True

    @classmethod
    def _calculate_checksum(cls, gstin_without_check: str) -> str:
        """
        Calculate checksum for GSTIN using Luhn algorithm variant

        Args:
            gstin_without_check: First 14 characters of GSTIN

        Returns:
            Expected checksum character
        """
        total = 0
        factor = 1

        for char in gstin_without_check:
            char_value = cls.CHAR_VALUES.get(char.upper(), 0)

            # Multiply by factor (alternating 1 and 2)
            digit = char_value * factor

            # Sum the digits if result > 35
            digit = (digit // 36) + (digit % 36)

            total += digit

            # Alternate factor between 1 and 2
            factor = 2 if factor == 1 else 1

        # Calculate checksum
        remainder = total % 36
        checksum_value = (36 - remainder) % 36

        # Convert back to character
        if checksum_value < 10:
            return str(checksum_value)
        else:
            return chr(ord('A') + checksum_value - 10)

    @classmethod
    def get_state_name(cls, gstin: str) -> Optional[str]:
        """Get state name from GSTIN"""
        if len(gstin) >= 2:
            state_code = gstin[:2]
            return STATE_CODES.get(state_code)
        return None

    @classmethod
    def get_pan(cls, gstin: str) -> Optional[str]:
        """Extract PAN from GSTIN"""
        if len(gstin) >= 12:
            return gstin[2:12].upper()
        return None

    @classmethod
    def get_entity_type(cls, gstin: str) -> Optional[str]:
        """Get entity type from GSTIN"""
        if len(gstin) >= 13:
            entity_code = gstin[12].upper()
            return ENTITY_CODES.get(entity_code, "Unknown")
        return None

    @classmethod
    def parse(cls, gstin: str) -> dict:
        """
        Parse GSTIN and return all components

        Returns dict with:
        - is_valid: bool
        - error: Optional error message
        - state_code: 2-digit state code
        - state_name: State name
        - pan: Extracted PAN
        - entity_code: Entity type code
        - entity_type: Entity type name
        - checksum: Checksum character
        """
        gstin = gstin.upper().strip()
        is_valid, error = cls.validate(gstin)

        result = {
            "gstin": gstin,
            "is_valid": is_valid,
            "error": error,
        }

        if len(gstin) >= 15:
            result.update({
                "state_code": gstin[:2],
                "state_name": cls.get_state_name(gstin),
                "pan": cls.get_pan(gstin),
                "entity_code": gstin[12] if len(gstin) >= 13 else None,
                "entity_type": cls.get_entity_type(gstin),
                "checksum": gstin[14] if len(gstin) >= 15 else None,
            })

        return result
