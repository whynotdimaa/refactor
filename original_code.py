import traceback
import bcrypt
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a3b1c4d8f2e9c6a8e5d7a9b2f3c4d6e9'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class MenuItem(db.Model):
    __tablename__ = 'menu_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    ingredients = db.Column(db.Text, nullable=True)
    calories = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Numeric(5, 2), nullable=True)
    availability = db.Column(db.Enum('доступно', 'недоступно', name='availability_enum'), default='доступно')
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
    status = db.Column(db.Enum('нове', 'готуватися', 'оплачено'), default='нове')
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Enum('готівка', 'картка', 'онлайн'), default='готівка')
    tips = db.Column(db.Numeric(10, 2), default=0.0)
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
    status = db.Column(db.Enum('вільний', 'заброньований', 'зайнятий', name='table_status_enum'), default='вільний')
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
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.Enum('готівка', 'картка', 'онлайн'), default='готівка', nullable=False)
    payment_status = db.Column(db.Enum('оплачено', 'очікує оплати'), default='очікує оплати')
    delivery_address = db.Column(db.String(255), nullable=True)
    contact_number = db.Column(db.String(20), nullable=True)
    delivery_notes = db.Column(db.Text, nullable=True)
    delivery_status = db.Column(db.Enum('в очікуванні', 'доставлено', 'скасовано'), default='в очікуванні')

    def __repr__(self):
        return f'<PaymentAndDelivery {self.id}>'


@app.before_request
def create_tables():
    db.create_all()

@app.route('/menu_items', methods=['GET'])
def menu_items_page():
    menu_items = MenuItem.query.all()
    return render_template('menu_items.html', menu_items=menu_items)


# Роут для отримання меню та рендерингу інтерфейсу
@app.route('/', methods=['GET'])
def Index():                                # SMELL 1: назва з великої літери, порушення PEP8
    menu_items = MenuItem.query.all()
    return render_template('index.html', menu_items=menu_items)


@app.route('/menu', methods=['POST'])
def add_menu_item():
    data = request.form
    if 'name' not in data or 'price' not in data:
        return jsonify({"error": "Missing name or price"}), 400

    # SMELL 2: дубльований код - ідентична логіка є в add_menu_item_form()
    new_item = MenuItem(
        name=data['name'],
        price=data['price'],
        ingredients=data.get('ingredients', ''),
        calories=data.get('calories'),
        weight=data.get('weight'),
        availability=data.get('availability', 'доступно'),
        category_id=data.get('category_id')
    )
    db.session.add(new_item)
    db.session.commit()
    return jsonify({"message": "Menu item added successfully"}), 201

@app.route('/add_menu_item', methods=['GET', 'POST'])
@login_required
def add_menu_item_form():
    if request.method == 'POST':
        data = request.form
        if 'name' not in data or 'price' not in data:
            flash('Вкажіть назву та ціну страви', 'error')
            return redirect(url_for('add_menu_item'))

        # SMELL 2 (продовження): дублювання логіки створення MenuItem
        new_item = MenuItem(
            name=data['name'],
            price=data['price'],
            ingredients=data.get('ingredients', ''),
            calories=data.get('calories'),
            weight=data.get('weight'),
            availability=data.get('availability', 'доступно'),
            category_id=data.get('category_id')
        )
        db.session.add(new_item)
        db.session.commit()
        flash('Страва успішно додана!', 'success')
        return redirect(url_for('menu_item_add'))

    menu_items = MenuItem.query.all()
    return render_template('add_menu_item.html', menu_items=menu_items)


@app.route('/menu/<int:item_id>', methods=['DELETE'])
@login_required
def delete_menu_item(item_id):
    item = MenuItem.query.get(item_id)      # SMELL 3: query.get() є застарілим у SQLAlchemy 2.x
    if not item:
        return jsonify({"error": "Menu item not found"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Menu item deleted successfully"}), 200


@app.route('/menu/<int:item_id>', methods=['PUT'])
@login_required
def update_menu_item(item_id):
    item = MenuItem.query.get(item_id)      # SMELL 3: query.get() застарілий
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

@app.route('/orders', methods=['GET'])
def get_orders():
    return render_template('orders.html')
    # SMELL 4: мертвий код — недосяжні рядки після return
    orders = Order.query.all()
    result = []
    for order in orders:
        result.append({
            'id': order.id,
            'customer_name': order.customer_name,
            'status': order.status,
            'total_price': float(order.total_price),
        })
    return jsonify(result)


@app.route('/create_order', methods=['POST'])
def create_order():
    data = request.get_json()

    try:
        order = Order(
            table_number=1,             # SMELL 5: магічне число — захардкожений номер столу
            order_time=datetime.utcnow(),
            status='нове',
            total_price=sum(item['price'] * item['quantity'] for item in data['order_items']),
            payment_method='готівка',   # SMELL 5: магічний рядок
            tips=0.0,
            customer_name=data['customer_name']
        )
        db.session.add(order)
        db.session.flush()

        for item in data['order_items']:
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=item['menu_item_id'],
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)

        db.session.commit()
        return jsonify({"message": "Order created successfully", "order_id": order.id}), 201

    except Exception as e:
        app.logger.error("Error creating order: %s", str(e))
        app.logger.error(traceback.format_exc())
        # SMELL 6: відсутній db.session.rollback() при помилці
        return jsonify({"message": "Error creating order", "error": str(e)}), 500


@app.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    order = Order.query.get(order_id)       # SMELL 3: query.get() застарілий
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    data = request.json
    # SMELL 7: перевірка статусів англійською, але БД зберігає українські значення
    if 'status' not in data or data['status'] not in ['new', 'in_progress', 'completed', 'cancelled']:
        return jsonify({'error': 'Invalid status'}), 400

    order.status = data['status']
    db.session.commit()
    return jsonify({'message': 'Order status updated successfully'}), 200


@app.route('/tables', methods=['POST'])
def add_table():
    data = request.json
    if 'number' not in data or 'capacity' not in data:
        return jsonify({"error": "Number and capacity are required"}), 400

    new_table = Table(
        number=data['number'],
        capacity=data['capacity'],
        status='вільний',
    )
    db.session.add(new_table)
    db.session.commit()
    return jsonify({"message": "Table added successfully"}), 201


@app.route('/tables/<int:table_id>', methods=['PUT'])
def update_table_status(table_id):
    table = Table.query.get(table_id)       # SMELL 3: query.get() застарілий
    if not table:
        return jsonify({"error": "Table not found"}), 404

    data = request.json
    if 'status' not in data or data['status'] not in ['вільний', 'заброньований', 'зайнятий']:
        return jsonify({"error": "Invalid status"}), 400

    table.status = data['status']
    table.reservation_time = data.get('reservation_time', table.reservation_time)
    table.notes = data.get('notes', table.notes)

    db.session.commit()
    return jsonify({"message": "Table status updated successfully"}), 200


@app.route('/tables', methods=['GET'])
def tables_page():
    tables = Table.query.all()
    return render_template('tables.html', tables=tables)


# SMELL 8: функція get_tables() визначена але не прив'язана до жодного маршруту (мертвий код)
def get_tables():
    tables = Table.query.all()
    result = [
        {
            'id': table.id,
            'number': table.number,
            'capacity': table.capacity,
            'status': table.status,
            'reservation_time': table.reservation_time.strftime(
                '%Y-%m-%d %H:%M:%S') if table.reservation_time else None,
            'notes': table.notes,
        }
        for table in tables
    ]
    return jsonify(result)

login_manager = LoginManager(app)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))     # SMELL 3: query.get() застарілий


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        username = request.form['username']

        if not username or not email or not password or not role:
            flash('Please fill in all fields', 'error')
            return redirect('/register')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email is already taken', 'error')
            return redirect('/register')

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        new_user = User(email=email, password=hashed_password, role=role, username=username)
        db.session.add(new_user)
        db.session.commit()

        flash('User registered successfully', 'success')
        return redirect('/login')

    return render_template('register.html')

# SMELL 9: дублювання маршруту '/' — функція home() ніколи не викликається
@app.route('/')
def home():
    user_logged_in = session.get('user_logged_in', False)
    return render_template('index.html', user_logged_in=user_logged_in)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect('/dashboard')
        else:
            flash('Login failed. Check your email and/or password', 'error')
            return redirect('/login')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))
    # SMELL 4 (продовження): мертвий код після return
    session.pop('user_logged_in', None)
    return "Ви успішно вийшли! <a href='/'>Повернутись на головну</a>"

@app.route('/dashboard')
@login_required
def dashboard():
    # SMELL 10: велика розгалужена умовна конструкція if/elif/elif
    if current_user.role == 'admin':
        return render_template('dashboard_admin.html', user=current_user)
    elif current_user.role == 'waiter':
        return render_template('dashboard_waiter.html', user=current_user)
    elif current_user.role == 'chef':
        return render_template('dashboard_chef.html', user=current_user)
    else:
        flash('Access denied', 'danger')
        return redirect(url_for('login'))


@app.route('/reviews', methods=['GET'])
def get_reviews():
    reviews = Review.query.all()
    # SMELL 11: дублювання серіалізації — ідентичний код є в reviews_page()
    result = [
        {
            'id': review.id,
            'user': review.user.username,
            'menu_item': review.menu_item.name if review.menu_item else None,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        for review in reviews
    ]
    return jsonify(result)

@app.route('/reviews_page', methods=['GET'])
def reviews_page():
    reviews = Review.query.all()
    menu_items = MenuItem.query.all()
    # SMELL 11 (продовження): та сама серіалізація відгуків — дублювання
    return render_template('reviews.html', reviews=[
        {
            'id': review.id,
            'user': review.user.username,
            'menu_item': review.menu_item.name if review.menu_item else None,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        } for review in reviews
    ], menu_items=menu_items)


@app.route('/reviews', methods=['POST'])
def add_review():
    try:
        menu_item_id = request.form.get('menu_item_id')
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment')

        if not menu_item_id or not rating or not comment:
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
    except Exception as e:
        app.logger.error(f"Error adding review: {e}")
        flash('Не вдалося додати відгук. Спробуйте ще раз.', 'error')

    return redirect(url_for('reviews_page'))

@app.route('/create_payment_delivery', methods=['GET', 'POST'])
def create_payment_delivery():
    if request.method == 'POST':
        order_id = request.form['order_id']
        payment_method = request.form['payment_method']
        delivery_address = request.form['delivery_address']
        contact_number = request.form['contact_number']

        new_payment_delivery = PaymentAndDelivery(
            order_id=order_id,
            payment_method=payment_method,
            delivery_address=delivery_address,
            contact_number=contact_number
        )

        try:
            db.session.add(new_payment_delivery)
            db.session.commit()
            return f"Запис з ID {order_id} успішно додано!"
        except Exception as e:
            db.session.rollback()
            return f"Сталася помилка при додаванні запису: {str(e)}"
    return render_template('create_payment_delivery.html')


@app.route('/update_payment_delivery/<int:id>', methods=['PUT'])
def update_payment_delivery(id):
    payment_delivery = PaymentAndDelivery.query.get(id)     # SMELL 3: query.get() застарілий
    if not payment_delivery:
        return jsonify({"error": "Payment and delivery record not found"}), 404

    data = request.json
    payment_delivery.payment_status = data.get('payment_status', payment_delivery.payment_status)
    payment_delivery.delivery_status = data.get('delivery_status', payment_delivery.delivery_status)
    payment_delivery.delivery_notes = data.get('delivery_notes', payment_delivery.delivery_notes)

    db.session.commit()
    return jsonify({"message": "Payment and delivery updated successfully"}), 200

# SMELL 9: дублювання маршруту /payment_delivery GET — Flask виконає лише перший
@app.route('/payment_delivery', methods=['GET'])
@login_required
def payment_delivery_page():
    records = PaymentAndDelivery.query.all()
    return render_template('payment_delivery_page.html', records=[
        {
            'id': record.id,
            'order_id': record.order_id,
            'payment_method': record.payment_method,
            'payment_status': record.payment_status,
            'delivery_address': record.delivery_address,
            'contact_number': record.contact_number,
            'delivery_status': record.delivery_status,
            'delivery_notes': record.delivery_notes,
        } for record in records
    ])


@app.route('/payment_delivery', methods=['GET'])
def get_all_payments_deliveries():
    records = PaymentAndDelivery.query.all()
    result = [
        {
            'id': record.id,
            'order_id': record.order_id,
            'payment_method': record.payment_method,
            'payment_status': record.payment_status,
            'delivery_address': record.delivery_address,
            'contact_number': record.contact_number,
            'delivery_status': record.delivery_status,
            'delivery_notes': record.delivery_notes,
        } for record in records
    ]
    return jsonify(result)

@app.route('/payment_delivery_form', methods=['GET'])
def payment_delivery_form():
    return render_template('create_payment_delivery.html')

if __name__ == '__main__':
    app.run(debug=True)
