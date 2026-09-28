from uuid import UUID
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from bancocloud.api.cors import allowed_origins
from bancocloud.api.dependencies import require_demo_key
from bancocloud.api.schemas.accounts import OnboardingRequest
from bancocloud.api.schemas.cards import CardPurchaseRequest
from bancocloud.api.schemas.cases import AnalystDecisionRequest
from bancocloud.api.schemas.loans import LoanApplicationRequest
from bancocloud.api.schemas.transfers import TransferRequest
from bancocloud.application.accounts_service import AccountsService
from bancocloud.application.cards_service import CardsService
from bancocloud.application.cases_service import CaseContractError, CaseReferenceError, CasesService
from bancocloud.application.loans_service import LoansService
from bancocloud.application.onboarding_service import OnboardingService
from bancocloud.application.transfers_service import TransfersService
from bancocloud.domain.cards import CardError
from bancocloud.domain.loans import LoanError
from bancocloud.domain.onboarding import OnboardingError
from bancocloud.domain.transfers import TransferCommand, TransferError
from bancocloud.infrastructure.postgres.connection import connect
from bancocloud.infrastructure.postgres.repositories.accounts import PostgresAccountRepository
from bancocloud.infrastructure.postgres.repositories.cards import PostgresCardRepository
from bancocloud.infrastructure.postgres.repositories.cases import PostgresCaseRepository
from bancocloud.infrastructure.postgres.repositories.loans import PostgresLoanRepository
from bancocloud.infrastructure.postgres.repositories.onboarding import PostgresOnboardingRepository
from bancocloud.infrastructure.postgres.repositories.transactions import PostgresTransactionRepository

app = FastAPI(title="BancoCloud Core Modular LOCAL FIRST", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "Idempotency-Key", "X-Demo-Key"],
)
_secure = [Depends(require_demo_key)]

accounts_service = AccountsService(PostgresAccountRepository())
cards_service = CardsService(PostgresCardRepository())
cases_service = CasesService(PostgresCaseRepository())
loans_service = LoansService(PostgresLoanRepository())
onboarding_service = OnboardingService(PostgresOnboardingRepository())
transfers_service = TransfersService(PostgresTransactionRepository())


@app.get("/health")
def health():
    with connect() as conn: conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.get("/accounts", dependencies=_secure)
def accounts(customer_ref: UUID | None = None):
    return accounts_service.list_accounts(customer_ref)


@app.get("/accounts/{account_ref}/movements", dependencies=_secure)
def movements(account_ref: UUID, limit: int = 50):
    return accounts_service.movements(account_ref, limit)


@app.post("/onboarding", dependencies=_secure)
def onboarding(request: OnboardingRequest):
    try: return onboarding_service.onboard(request.region)
    except OnboardingError as exc: raise HTTPException(400, str(exc)) from exc


@app.get("/cards", dependencies=_secure)
def cards(customer_ref: UUID | None = None, account_ref: UUID | None = None):
    return cards_service.list_cards(customer_ref, account_ref)


@app.post("/cards/purchase", dependencies=_secure)
def purchase(request: CardPurchaseRequest):
    try: return cards_service.purchase(request.card_ref, request.amount, request.currency.upper())
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except CardError as exc: raise HTTPException(400, str(exc)) from exc


@app.get("/loans", dependencies=_secure)
def loans(customer_ref: UUID | None = None, account_ref: UUID | None = None):
    return loans_service.list_loans(customer_ref, account_ref)


@app.post("/loans/apply", dependencies=_secure)
def apply_loan(request: LoanApplicationRequest):
    try: return loans_service.apply(request.account_ref, request.amount, request.term_months, request.monthly_income)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except (LoanError, ValueError) as exc: raise HTTPException(400, str(exc)) from exc


@app.get("/cases", dependencies=_secure)
def cases(limit: int = 100):
    return cases_service.list_cases(limit)


@app.post("/cases/{case_id}/decision", dependencies=_secure)
def decide(case_id: UUID, request: AnalystDecisionRequest):
    try:
        return cases_service.record_decision(case_id, request.model_dump(mode="json"))
    except CaseContractError as exc:
        raise HTTPException(422, str(exc)) from exc
    except CaseReferenceError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/transfers", dependencies=_secure)
def transfer(request: TransferRequest, idempotency_key: UUID = Header(...)):
    command = TransferCommand(request.source_account, request.destination_account, request.amount,
                              request.device_ref, request.beneficiary_ref)
    try: return transfers_service.transfer(command, idempotency_key)
    except TransferError as exc:
        code = 409 if "Idempotency key" in str(exc) else 400
        raise HTTPException(code, str(exc)) from exc
