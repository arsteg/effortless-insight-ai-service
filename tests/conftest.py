"""
Test configuration and fixtures
"""

import pytest
import asyncio
from typing import AsyncGenerator
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.core.database import Base, get_db


# Test database URL (use in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client() -> TestClient:
    """Create test client"""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_notice_id():
    """Generate sample notice ID"""
    return uuid4()


@pytest.fixture
def sample_gstin():
    """Sample valid GSTIN"""
    return "29AADCB2230M1ZV"


@pytest.fixture
def sample_notice_text():
    """Sample GST notice text for testing"""
    return """
    GOVERNMENT OF INDIA
    OFFICE OF THE COMMISSIONER OF CGST

    Notice Number: DRC-01/2024/123456
    Date: 15/01/2024

    To:
    M/s Sample Company Pvt Ltd
    GSTIN: 29AADCB2230M1ZV

    Subject: Show Cause Notice under Section 73 of CGST Act, 2017

    This is to inform you that during the scrutiny of your returns for the period
    April 2023 to September 2023, the following discrepancies were noticed:

    1. Short payment of CGST: Rs. 5,00,000/-
    2. Short payment of SGST: Rs. 5,00,000/-
    3. Interest payable: Rs. 75,000/-
    4. Penalty: Rs. 50,000/-

    Total Demand: Rs. 10,25,000/-

    You are hereby directed to submit your reply within 30 days from the date
    of receipt of this notice, i.e., by 14/02/2024.

    Failure to comply may result in ex-parte order under Section 73(9) of CGST Act.

    Reference: Rule 142 of CGST Rules, 2017

    Sd/-
    Assistant Commissioner
    CGST Division, Bangalore
    """


@pytest.fixture
def sample_extracted_entities():
    """Sample extracted entities"""
    from datetime import date
    from app.schemas.entities import ExtractedEntities, GSTINInfo, DateInfo, AmountInfo, DateType, AmountType

    return ExtractedEntities(
        gstins=[
            GSTINInfo(
                gstin="29AADCB2230M1ZV",
                is_valid=True,
                state_code="29",
                state_name="Karnataka",
                pan="AADCB2230M",
                entity_type="Company",
                position_in_text=150,
                confidence=0.95,
            )
        ],
        dates=[
            DateInfo(
                date=date(2024, 1, 15),
                date_type=DateType.ISSUE_DATE,
                original_text="15/01/2024",
                position_in_text=80,
                confidence=0.95,
            ),
            DateInfo(
                date=date(2024, 2, 14),
                date_type=DateType.RESPONSE_DEADLINE,
                original_text="14/02/2024",
                position_in_text=550,
                confidence=0.95,
            ),
        ],
        amounts=[
            AmountInfo(
                amount=500000.0,
                amount_type=AmountType.TAX,
                original_text="Rs. 5,00,000/-",
                position_in_text=300,
                confidence=0.95,
            ),
            AmountInfo(
                amount=1025000.0,
                amount_type=AmountType.TOTAL,
                original_text="Rs. 10,25,000/-",
                position_in_text=450,
                confidence=0.95,
            ),
        ],
        sections=[],
        primary_gstin="29AADCB2230M1ZV",
        issue_date=date(2024, 1, 15),
        response_deadline=date(2024, 2, 14),
        tax_amount=500000.0,
        total_amount=1025000.0,
    )
