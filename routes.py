from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, LeaveRequest, Payroll
from datetime import datetime, date

main = Blueprint('main', __name__)

FREE_LEAVES_PER_MONTH = 2

def recalculate_payroll(employee_id, month, year):
    """Recalculate payroll for a given employee/month/year based on approved leaves."""
    employee = User.query.get(employee_id)
    if not employee:
        return

    approved_leaves = LeaveRequest.query.filter_by(
        employee_id=employee_id,
        month=month,
        year=year,
        status='approved'
    ).count()

    extra_leaves = max(0, approved_leaves - FREE_LEAVES_PER_MONTH)
    # Deduct per extra leave day: base_salary / 30 per day
    per_day = employee.base_salary / 30
    deduction = extra_leaves * per_day
    net_salary = employee.base_salary - deduction

    payroll = Payroll.query.filter_by(
        employee_id=employee_id,
        month=month,
        year=year
    ).first()

    if payroll:
        payroll.leaves_taken = approved_leaves
        payroll.deduction = round(deduction, 2)
        payroll.net_salary = round(net_salary, 2)
        payroll.base_salary = employee.base_salary
        payroll.updated_at = datetime.utcnow()
    else:
        payroll = Payroll(
            employee_id=employee_id,
            month=month,
            year=year,
            base_salary=employee.base_salary,
            leaves_taken=approved_leaves,
            deduction=round(deduction, 2),
            net_salary=round(net_salary, 2)
        )
        db.session.add(payroll)

    db.session.commit()


# ─── Auth Routes ────────────────────────────────────────────────────────────────

@main.route('/', methods=['GET', 'POST'])
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm  = request.form.get('confirm_password', '').strip()

        if not username or not password:
            flash('Username and password are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 4:
            flash('Password must be at least 4 characters.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.', 'error')
        else:
            new_user = User(username=username, role='employee', base_salary=50000.0)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('main.login'))

    return render_template('register.html')


@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))


@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('main.admin_dashboard'))
    return redirect(url_for('main.employee_dashboard'))


# ─── Employee Routes ─────────────────────────────────────────────────────────────

@main.route('/employee/dashboard')
@login_required
def employee_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('main.admin_dashboard'))

    now = datetime.utcnow()
    my_leaves = LeaveRequest.query.filter_by(
        employee_id=current_user.id,
        month=now.month,
        year=now.year
    ).order_by(LeaveRequest.created_at.desc()).all()

    payroll = Payroll.query.filter_by(
        employee_id=current_user.id,
        month=now.month,
        year=now.year
    ).first()

    return render_template('employee_dashboard.html',
                           leaves=my_leaves,
                           payroll=payroll,
                           now=now)


@main.route('/employee/leave', methods=['GET', 'POST'])
@login_required
def leave():
    if current_user.role == 'admin':
        return redirect(url_for('main.admin_dashboard'))

    now = datetime.utcnow()

    if request.method == 'POST':
        leave_date_str = request.form.get('leave_date', '').strip()
        reason = request.form.get('reason', '').strip()

        if not leave_date_str or not reason:
            flash('Please provide both a leave date and a reason.', 'error')
        else:
            try:
                leave_date = datetime.strptime(leave_date_str, '%Y-%m-%d').date()
                # Check for duplicate
                existing = LeaveRequest.query.filter_by(
                    employee_id=current_user.id,
                    leave_date=leave_date
                ).first()
                if existing:
                    flash('You have already applied for leave on this date.', 'error')
                else:
                    lr = LeaveRequest(
                        employee_id=current_user.id,
                        leave_date=leave_date,
                        reason=reason,
                        month=leave_date.month,
                        year=leave_date.year,
                        status='pending'
                    )
                    db.session.add(lr)
                    db.session.commit()
                    flash('Leave request submitted successfully!', 'success')
                    return redirect(url_for('main.leave'))
            except ValueError:
                flash('Invalid date format.', 'error')

    my_leaves = LeaveRequest.query.filter_by(
        employee_id=current_user.id
    ).order_by(LeaveRequest.leave_date.desc()).all()

    # Count approved leaves this month
    approved_this_month = LeaveRequest.query.filter_by(
        employee_id=current_user.id,
        month=now.month,
        year=now.year,
        status='approved'
    ).count()

    return render_template('leave.html',
                           leaves=my_leaves,
                           approved_this_month=approved_this_month,
                           free_leaves=FREE_LEAVES_PER_MONTH,
                           now=now)


@main.route('/employee/payroll')
@login_required
def payroll():
    if current_user.role == 'admin':
        return redirect(url_for('main.admin_dashboard'))

    now = datetime.utcnow()

    # Ensure payroll record exists
    recalculate_payroll(current_user.id, now.month, now.year)

    current_payroll = Payroll.query.filter_by(
        employee_id=current_user.id,
        month=now.month,
        year=now.year
    ).first()

    all_payroll = Payroll.query.filter_by(
        employee_id=current_user.id
    ).order_by(Payroll.year.desc(), Payroll.month.desc()).all()

    return render_template('payroll.html',
                           current_payroll=current_payroll,
                           all_payroll=all_payroll,
                           now=now)


# ─── Admin Routes ─────────────────────────────────────────────────────────────────

@main.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('main.employee_dashboard'))

    now = datetime.utcnow()
    pending_leaves = LeaveRequest.query.filter_by(status='pending').order_by(LeaveRequest.created_at.desc()).all()
    all_employees = User.query.filter_by(role='employee').all()

    # Gather payroll summary
    payroll_summary = []
    for emp in all_employees:
        recalculate_payroll(emp.id, now.month, now.year)
        p = Payroll.query.filter_by(employee_id=emp.id, month=now.month, year=now.year).first()
        payroll_summary.append({'employee': emp, 'payroll': p})

    return render_template('admin_dashboard.html',
                           pending_leaves=pending_leaves,
                           payroll_summary=payroll_summary,
                           now=now)


@main.route('/admin/leave/<int:leave_id>/<action>', methods=['POST'])
@login_required
def handle_leave(leave_id, action):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('main.employee_dashboard'))

    lr = LeaveRequest.query.get_or_404(leave_id)

    if action == 'approve':
        lr.status = 'approved'
        flash(f'Leave request approved for {lr.employee.username}.', 'success')
    elif action == 'reject':
        lr.status = 'rejected'
        flash(f'Leave request rejected for {lr.employee.username}.', 'info')
    else:
        flash('Invalid action.', 'error')
        return redirect(url_for('main.admin_dashboard'))

    db.session.commit()
    recalculate_payroll(lr.employee_id, lr.month, lr.year)
    return redirect(url_for('main.admin_dashboard'))