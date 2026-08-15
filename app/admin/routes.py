from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.extensions import db
from app.models.user import User
from app.models.loan import LoanApplication
from app.models.payment import PaymentTransaction


bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
)


# ============================================================
# ADMIN SESSION PROTECTION
# ============================================================

def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if not session.get("admin_authenticated"):
            abort(403)

        return view(*args, **kwargs)

    return wrapped_view


# ============================================================
# SECRET ADMIN ENTRY URL
# ============================================================

@bp.route("/<admin_key>")
def admin_entry(admin_key):

    configured_key = current_app.config.get(
        "ADMIN_URL_KEY"
    )

    if not configured_key:
        abort(404)

    if admin_key != configured_key:
        abort(404)

    session["admin_authenticated"] = True
    session.permanent = True

    return redirect(
        url_for("admin.dashboard")
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@bp.route("/logout")
@admin_required
def logout():

    session.pop(
        "admin_authenticated",
        None,
    )

    return redirect(
        url_for("main.landing")
    )


# ============================================================
# DASHBOARD
# ============================================================

@bp.route("")
@admin_required
def dashboard():

    total_users = User.query.count()

    active_users = User.query.filter_by(
        is_active_flag=True
    ).count()

    total_loans = LoanApplication.query.count()

    pending_loans = LoanApplication.query.filter(
        LoanApplication.status.in_([
            "SUBMITTED",
            "PAYMENT_PENDING",
        ])
    ).count()

    approved_loans = LoanApplication.query.filter(
        LoanApplication.status == "PAYMENT_SUCCESS"
    ).count()

    failed_loans = LoanApplication.query.filter(
        LoanApplication.status.in_([
            "PAYMENT_FAILED",
            "PAYMENT_CANCELLED",
        ])
    ).count()

    total_payments = PaymentTransaction.query.count()

    successful_payments = PaymentTransaction.query.filter_by(
        status="SUCCESS"
    ).count()

    pending_payments = PaymentTransaction.query.filter_by(
        status="PENDING"
    ).count()

    total_loan_amount = db.session.query(
        db.func.coalesce(
            db.func.sum(
                LoanApplication.loan_amount
            ),
            0,
        )
    ).scalar()

    total_payment_amount = db.session.query(
        db.func.coalesce(
            db.func.sum(
                PaymentTransaction.amount
            ),
            0,
        )
    ).filter(
        PaymentTransaction.status == "SUCCESS"
    ).scalar()

    recent_loans = (
        LoanApplication.query
        .order_by(
            LoanApplication.created_at.desc()
        )
        .limit(10)
        .all()
    )

    recent_payments = (
        PaymentTransaction.query
        .order_by(
            PaymentTransaction.created_at.desc()
        )
        .limit(10)
        .all()
    )

    return render_template(
        "admin/dashboard.html",

        total_users=total_users,
        active_users=active_users,

        total_loans=total_loans,
        pending_loans=pending_loans,
        approved_loans=approved_loans,
        failed_loans=failed_loans,

        total_payments=total_payments,
        successful_payments=successful_payments,
        pending_payments=pending_payments,

        total_loan_amount=total_loan_amount or 0,
        total_payment_amount=total_payment_amount or 0,

        recent_loans=recent_loans,
        recent_payments=recent_payments,
    )


# ============================================================
# USERS
# ============================================================

@bp.route("/users")
@admin_required
def users():

    search = request.args.get(
        "search",
        "",
        type=str,
    ).strip()

    query = User.query

    if search:
        query = query.filter(
            db.or_(
                User.full_name.ilike(
                    f"%{search}%"
                ),
                User.email.ilike(
                    f"%{search}%"
                ),
                User.phone.ilike(
                    f"%{search}%"
                ),
            )
        )

    users = (
        query
        .order_by(
            User.created_at.desc()
        )
        .all()
    )

    return render_template(
        "admin/users.html",
        users=users,
        search=search,
    )


# ============================================================
# USER DETAILS
# ============================================================

@bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):

    user = User.query.get_or_404(
        user_id
    )

    loans = (
        LoanApplication.query
        .filter_by(
            user_id=user.id
        )
        .order_by(
            LoanApplication.created_at.desc()
        )
        .all()
    )

    return render_template(
        "admin/user_detail.html",
        user=user,
        loans=loans,
    )


# ============================================================
# LOANS
# ============================================================

@bp.route("/loans")
@admin_required
def loans():

    search = request.args.get(
        "search",
        "",
        type=str,
    ).strip()

    status = request.args.get(
        "status",
        "",
        type=str,
    ).strip()

    query = LoanApplication.query

    if search:
        query = query.filter(
            db.or_(
                LoanApplication.application_number.ilike(
                    f"%{search}%"
                ),
                LoanApplication.full_name.ilike(
                    f"%{search}%"
                ),
                LoanApplication.phone.ilike(
                    f"%{search}%"
                ),
                LoanApplication.email.ilike(
                    f"%{search}%"
                ),
            )
        )

    if status:
        query = query.filter(
            LoanApplication.status == status
        )

    loans = (
        query
        .order_by(
            LoanApplication.created_at.desc()
        )
        .all()
    )

    statuses = [
        "DRAFT",
        "SUBMITTED",
        "PAYMENT_PENDING",
        "PAYMENT_SUCCESS",
        "PAYMENT_FAILED",
        "PAYMENT_CANCELLED",
    ]

    return render_template(
        "admin/loans.html",
        loans=loans,
        search=search,
        selected_status=status,
        statuses=statuses,
    )


# ============================================================
# LOAN DETAILS
# ============================================================

@bp.route("/loans/<int:loan_id>")
@admin_required
def loan_detail(loan_id):

    loan = LoanApplication.query.get_or_404(
        loan_id
    )

    transactions = (
        PaymentTransaction.query
        .filter_by(
            application_id=loan.id
        )
        .order_by(
            PaymentTransaction.created_at.desc()
        )
        .all()
    )

    return render_template(
        "admin/loan_detail.html",
        loan=loan,
        transactions=transactions,
    )


# ============================================================
# PAYMENTS
# ============================================================

@bp.route("/payments")
@admin_required
def payments():

    status = request.args.get(
        "status",
        "",
        type=str,
    ).strip()

    query = PaymentTransaction.query

    if status:
        query = query.filter(
            PaymentTransaction.status == status
        )

    payments = (
        query
        .order_by(
            PaymentTransaction.created_at.desc()
        )
        .all()
    )

    statuses = [
        "PENDING",
        "SUCCESS",
        "FAILED",
        "CANCELLED",
    ]

    return render_template(
        "admin/payments.html",
        payments=payments,
        statuses=statuses,
        selected_status=status,
    )


# ============================================================
# SETTINGS
# ============================================================

@bp.route("/settings")
@admin_required
def settings():

    return render_template(
        "admin/settings.html",
        config=current_app.config,
    )
