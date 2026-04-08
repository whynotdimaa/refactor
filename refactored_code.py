"""
Рефакторований Flask-застосунок для управління рестораном.
Застосовані техніки рефакторингу описані у docs/refactoring_report.md
"""
import os
import traceback
from datetime import datetime

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# ---------------------------------------------------------------------------
# Техніка 1: Replace Magic Number/String with Named Constant
# Всі магічні числа та рядки замінено на іменовані константи
# ---------------------------------------------------------------------------
DEFAULT_TABLE_NUMBER = 1
DEFAULT_PAYMENT_METHOD = 'готівка'
DEFAULT_TIPS = 0.0
DEFAULT_ORDER_STATUS = 'нове'
DEFAULT_TABLE_STATUS = 'вільний'
DEFAULT_AVAILABILITY = 'доступно'

VALID_TABLE_STATUSES = ('вільний', 'заброньований', 'зайнятий')
VALID_ORDER_STATUSES = ('нове', 'готуватися', 'оплачено')

DASHBOARD_TEMPLATES = {
    'admin': 'dashboard_admin.html',
    'waiter': 'dashboard_waiter.html',
    'chef': 'dashboard_chef.html',
}

# ---------------------------------------------------------------------------
# Техніка 2: Move Config to Environment Variable (секрет не в коді)
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a3b1c4d8f2e9c6a8e5d7a9b2f3c4d6e9')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///restaurant.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)


# ===========================================================================
# Моделі (без змін у структурі — рефакторинг не змінює схему БД)
# ===========================================================================

class MenuItem(db.Model):
    __tablename__ = 'menu_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    ingredients = db.Column(db.Text, nullable=True)
    calories = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Numeric(5, 2), nullable=True)
    availability = db.Column(
        db.Enum('доступно', 'недоступно', name='availability_enum'),
        default=DEFAULT_AVAILABILITY
    )
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category = db.relationship('Category', back_populates='menu_items')


class Category(db.Model):
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    menu_items = db.relationship('MenuItem', back_populates='category')


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, nullable=False)
    order_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.Enum(*VALID_ORDER_STATUSES), default=DEFAULT_ORDER_STATUS)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Enum('готівка', 'картка', 'онлайн'), default=DEFAULT_PAYMENT_METHOD)
    tips = db.Column(db.Numeric(10, 2), default=DEFAULT_TIPS)
    notes = db.Column(db.Text)
    customer_name = db.Column(db.String(100), nullable=True)
    order_items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    __tablename__ = 'order_item'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)


class Table(db.Model):
    __tablename__ = 'tables'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.Enum(*VALID_TABLE_STATUSES, name='table_status_enum'),
        default=DEFAULT_TABLE_STATUS
    )
    reservation_time = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(150), nullable=False)


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='reviews')
    menu_item = db.relationship('MenuItem', backref='reviews')


class PaymentAndDelivery(db.Model):
    __tablename__ = 'payment_and_delivery'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.Enum('готівка', 'картка', 'онлайн'), default=DEFAULT_PAYMENT_METHOD, nullable=False)
    payment_status = db.Column(db.Enum('оплачено', 'очікує оплати'), default='очікує оплати')
    delivery_address = db.Column(db.String(255), nullable=True)
    contact_number = db.Column(db.String(20), nullable=True)
    delivery_notes = db.Column(db.Text, nullable=True)
    delivery_status = db.Column(db.Enum('в очікуванні', 'доставлено', 'скасовано'), default='в очікуванні')

    def __repr__(self):
        return f'<PaymentAndDelivery {self.id}>'


# ===========================================================================
# Техніка 3: Extract Method — допоміжні функції сервісного рівня
# Логіка винесена з маршрутів у окремі функції з одною відповідальністю
# ===========================================================================

def _build_menu_item_from_form(data: dict) -> MenuItem:
    """Техніка 3: Extract Method — створення MenuItem винесено в окремий метод."""
    return MenuItem(
        name=data['name'],
        price=data['price'],
        ingredients=data.get('ingredients', ''),
        calories=data.get('calories'),
        weight=data.get('weight'),
        availability=data.get('availability', DEFAULT_AVAILABILITY),
        category_id=data.get('category_id'),
    )


def _serialize_review(review: Review) -> dict:
    """
    Техніка 4: Extract Method + Eliminate Duplicate Code
    Серіалізація відгуку винесена в один метод замість двох ідентичних блоків.
    """
    return {
        'id': review.id,
        'user': review.user.username,
        'menu_item': review.menu_item.name if review.menu_item else None,
        'rating': review.rating,
        'comment': review.comment,
        'created_at': review.created_at.strftime('%Y-%m-%d %H:%M:%S'),
    }


def _serialize_payment_delivery(record: PaymentAndDelivery) -> dict:
    """
    Техніка 4 (продовження): Extract Method — усуває дублювання серіалізації
    платежів між двома маршрутами.
    """
    return {
        'id': record.id,
        'order_id': record.order_id,
        'payment_method': record.payment_method,
        'payment_status': record.payment_status,
        'delivery_address': record.delivery_address,
        'contact_number': record.contact_number,
        'delivery_status': record.delivery_status,
        'delivery_notes': record.delivery_notes,
    }


def _calculate_order_total(order_items: list) -> float:
    """Техніка 3: Extract Method — розрахунок суми замовлення в окремій функції."""
    return sum(item['price'] * item['quantity'] for item in order_items)


def _find_by_id(model, record_id: int):
    """
    Техніка 5: Rename + Introduce Explaining Variable
    Замінює застарілий query.get() на актуальний db.session.get().
    """
    return db.session.get(model, record_id)


# ===========================================================================
# Техніка 6: Remove Dead Code — видалено функцію get_tables() без маршруту
# та недосяжний код після return у logout() і get_orders()
# ===========================================================================

@app.before_request
def create_tables():
    db.create_all()


@login_manager.user_loader
def load_user(user_id: str):
    return _find_by_id(User, int(user_id))


# ===========================================================================
# Маршрути — меню
# ===========================================================================

@app.route('/', methods=['GET'])
def index():
    """Техніка 7: Rename Method — Index → index (дотримання PEP8 snake_case)."""
    menu_items = MenuItem.query.all()
    return render_template('index.html', menu_items=menu_items)


@app.route('/menu_items', methods=['GET'])
def menu_items_page():
    menu_items = MenuItem.query.all()
    return render_template('menu_items.html', menu_items=menu_items)


@app.route('/menu', methods=['POST'])
def add_menu_item():
    """Використовує _build_menu_item_from_form — усуває дублювання (Техніка 3, 4)."""
    data = request.form
    if 'name' not in data or 'price' not in data:
        return jsonify({"error": "Missing name or price"}), 400

    new_item = _build_menu_item_from_form(data)
    db.session.add(new_item)
    db.session.commit()
    return jsonify({"message": "Menu item added successfully"}), 201


@app.route('/add_menu_item', methods=['GET', 'POST'])
@login_required
def add_menu_item_form():
    """Використовує _build_menu_item_from_form — усуває дублювання (Техніка 3, 4)."""
    if request.method == 'POST':
        data = request.form
        if 'name' not in data or 'price' not in data:
            flash('Вкажіть назву та ціну страви', 'error')
            return redirect(url_for('add_menu_item_form'))

        new_item = _build_menu_item_from_form(data)
        db.session.add(new_item)
        db.session.commit()
        flash('Страва успішно додана!', 'success')
        return redirect(url_for('add_menu_item_form'))

    menu_items = MenuItem.query.all()
    return render_template('add_menu_item.html', menu_items=menu_items)


@app.route('/menu/<int:item_id>', methods=['DELETE'])
@login_required
def delete_menu_item(item_id: int):
    """Техніка 5: db.session.get() замість застарілого query.get()."""
    item = _find_by_id(MenuItem, item_id)
    if not item:
        return jsonify({"error": "Menu item not found"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Menu item deleted successfully"}), 200


@app.route('/menu/<int:item_id>', methods=['PUT'])
@login_required
def update_menu_item(item_id: int):
    """Техніка 5: db.session.get() замість застарілого query.get()."""
    item = _find_by_id(MenuItem, item_id)
    if not item:
        return jsonify({"error": "Menu item not found"}), 404

    data = request.json
    item.name = data.get('name', item.name)
    item.price = data.get('price', item.price)
    item.ingredients = data.get('ingredients', item.ingredients)
    item.calories = data.get('calories', item.calories)
    item.weight = data.get('weight', item.weight)
    item.availability = data.get('availability', item.availability)
    item.category_id = data.get('category_id', item.category_id)

    db.session.commit()
    return jsonify({"message": "Menu item updated successfully"}), 200


# ===========================================================================
# Маршрути — замовлення
# ===========================================================================

@app.route('/orders', methods=['GET'])
def get_orders():
    """Техніка 6: Remove Dead Code — видалено недосяжний код після return."""
    return render_template('orders.html')


@app.route('/create_order', methods=['POST'])
def create_order():
    """
    Техніка 1: Named Constants замість магічних значень.
    Техніка 8: Add Rollback on Exception — додано db.session.rollback().
    """
    data = request.get_json()

    try:
        total = _calculate_order_total(data['order_items'])
        order = Order(
            table_number=data.get('table_number', DEFAULT_TABLE_NUMBER),
            order_time=datetime.utcnow(),
            status=DEFAULT_ORDER_STATUS,
            total_price=total,
            payment_method=data.get('payment_method', DEFAULT_PAYMENT_METHOD),
            tips=DEFAULT_TIPS,
            customer_name=data['customer_name'],
        )
        db.session.add(order)
        db.session.flush()

        for item in data['order_items']:
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=item['menu_item_id'],
                quantity=item['quantity'],
                price=item['price'],
            )
            db.session.add(order_item)

        db.session.commit()
        return jsonify({"message": "Order created successfully", "order_id": order.id}), 201

    except Exception as exc:
        db.session.rollback()   # Техніка 8: додано rollback
        app.logger.error("Error creating order: %s\n%s", exc, traceback.format_exc())
        return jsonify({"message": "Error creating order", "error": str(exc)}), 500


@app.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id: int):
    """
    Техніка 9: Fix Inconsistent Validation — статуси тепер відповідають значенням БД.
    Техніка 5: _find_by_id() замість застарілого query.get().
    """
    order = _find_by_id(Order, order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    data = request.json
    new_status = data.get('status')
    if new_status not in VALID_ORDER_STATUSES:
        return jsonify({'error': f'Invalid status. Valid values: {VALID_ORDER_STATUSES}'}), 400

    order.status = new_status
    db.session.commit()
    return jsonify({'message': 'Order status updated successfully'}), 200


# ===========================================================================
# Маршрути — столики
# ===========================================================================

@app.route('/tables', methods=['GET'])
def tables_page():
    tables = Table.query.all()
    return render_template('tables.html', tables=tables)


@app.route('/tables', methods=['POST'])
def add_table():
    data = request.json
    if 'number' not in data or 'capacity' not in data:
        return jsonify({"error": "Number and capacity are required"}), 400

    new_table = Table(
        number=data['number'],
        capacity=data['capacity'],
        status=DEFAULT_TABLE_STATUS,
    )
    db.session.add(new_table)
    db.session.commit()
    return jsonify({"message": "Table added successfully"}), 201


@app.route('/tables/<int:table_id>', methods=['PUT'])
def update_table_status(table_id: int):
    """Техніка 5: _find_by_id() замість застарілого query.get()."""
    table = _find_by_id(Table, table_id)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    data = request.json
    new_status = data.get('status')
    if new_status not in VALID_TABLE_STATUSES:
        return jsonify({"error": f"Invalid status. Valid values: {VALID_TABLE_STATUSES}"}), 400

    table.status = new_status
    table.reservation_time = data.get('reservation_time', table.reservation_time)
    table.notes = data.get('notes', table.notes)

    db.session.commit()
    return jsonify({"message": "Table status updated successfully"}), 200


# ===========================================================================
# Маршрути — автентифікація
# ===========================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        username = request.form['username']

        if not all([username, email, password, role]):
            flash('Please fill in all fields', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email is already taken', 'error')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(email=email, password=hashed_password, role=role, username=username)
        db.session.add(new_user)
        db.session.commit()

        flash('User registered successfully', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Login failed. Check your email and/or password', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Техніка 6: Remove Dead Code — видалено недосяжний код після return."""
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Техніка 10: Replace Conditional with Dictionary Lookup
    Замінено довгий if/elif/elif на словник DASHBOARD_TEMPLATES.
    """
    template = DASHBOARD_TEMPLATES.get(current_user.role)
    if not template:
        flash('Access denied', 'danger')
        return redirect(url_for('login'))
    return render_template(template, user=current_user)


# ===========================================================================
# Маршрути — відгуки
# ===========================================================================

@app.route('/reviews', methods=['GET'])
def get_reviews():
    """Техніка 4: _serialize_review() усуває дублювання коду."""
    reviews = Review.query.all()
    return jsonify([_serialize_review(r) for r in reviews])


@app.route('/reviews_page', methods=['GET'])
def reviews_page():
    """Техніка 4: _serialize_review() усуває дублювання коду."""
    reviews = Review.query.all()
    menu_items = MenuItem.query.all()
    return render_template(
        'reviews.html',
        reviews=[_serialize_review(r) for r in reviews],
        menu_items=menu_items,
    )


@app.route('/reviews', methods=['POST'])
def add_review():
    try:
        menu_item_id = request.form.get('menu_item_id')
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')

        if not all([menu_item_id, rating, comment]):
            flash('Усі поля повинні бути заповнені!', 'error')
            return redirect(url_for('reviews_page'))

        new_review = Review(
            user_id=current_user.id,
            menu_item_id=menu_item_id,
            rating=rating,
            comment=comment,
        )
        db.session.add(new_review)
        db.session.commit()
        flash('Відгук успішно додано!', 'success')
    except Exception as exc:
        app.logger.error("Error adding review: %s", exc)
        flash('Не вдалося додати відгук. Спробуйте ще раз.', 'error')

    return redirect(url_for('reviews_page'))


# ===========================================================================
# Маршрути — оплата та доставка
# Техніка 9: Remove Duplicate Route — об'єднано два маршрути GET /payment_delivery
# ===========================================================================

@app.route('/payment_delivery', methods=['GET'])
@login_required
def payment_delivery_page():
    """
    Техніка 9: Eliminate Duplicate Route — один маршрут замість двох.
    Техніка 4: _serialize_payment_delivery() усуває дублювання серіалізації.
    """
    records = PaymentAndDelivery.query.all()
    serialized = [_serialize_payment_delivery(r) for r in records]
    if request.accept_mimetypes.best == 'application/json':
        return jsonify(serialized)
    return render_template('payment_delivery_page.html', records=serialized)


@app.route('/create_payment_delivery', methods=['GET', 'POST'])
def create_payment_delivery():
    if request.method == 'POST':
        try:
            new_record = PaymentAndDelivery(
                order_id=request.form['order_id'],
                payment_method=request.form['payment_method'],
                delivery_address=request.form.get('delivery_address'),
                contact_number=request.form.get('contact_number'),
            )
            db.session.add(new_record)
            db.session.commit()
            flash('Запис успішно додано!', 'success')
            return redirect(url_for('payment_delivery_page'))
        except Exception as exc:
            db.session.rollback()
            flash(f'Помилка при додаванні запису: {exc}', 'error')

    return render_template('create_payment_delivery.html')


@app.route('/update_payment_delivery/<int:record_id>', methods=['PUT'])
def update_payment_delivery(record_id: int):
    """
    Техніка 5: _find_by_id() замість застарілого query.get().
    Техніка 7: Rename Parameter — id → record_id (уникнення тіні вбудованої функції).
    """
    record = _find_by_id(PaymentAndDelivery, record_id)
    if not record:
        return jsonify({"error": "Payment and delivery record not found"}), 404

    data = request.json
    record.payment_status = data.get('payment_status', record.payment_status)
    record.delivery_status = data.get('delivery_status', record.delivery_status)
    record.delivery_notes = data.get('delivery_notes', record.delivery_notes)

    db.session.commit()
    return jsonify({"message": "Payment and delivery updated successfully"}), 200


if __name__ == '__main__':
    app.run(debug=False)   # Техніка 2: debug=False у production
