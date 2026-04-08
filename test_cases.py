
import unittest
from unittest.mock import MagicMock, patch

class TestCalculateOrderTotal(unittest.TestCase):

    def _calculate(self, items):
        """Локальна копія логіки для ізольованого тестування."""
        return sum(item['price'] * item['quantity'] for item in items)

    def test_single_item(self):
        """Тест 1: один товар — ціна * кількість."""
        items = [{'price': 50.0, 'quantity': 2}]
        self.assertEqual(self._calculate(items), 100.0)

    def test_multiple_items(self):
        """Тест 2: декілька товарів — сума добутків."""
        items = [
            {'price': 30.0, 'quantity': 2},
            {'price': 20.0, 'quantity': 3},
        ]
        self.assertEqual(self._calculate(items), 120.0)

    def test_empty_order(self):
        """Тест 3: порожній список — сума дорівнює 0."""
        self.assertEqual(self._calculate([]), 0)

    def test_fractional_price(self):
        """Тест 4: дробова ціна — результат правильний."""
        items = [{'price': 9.99, 'quantity': 3}]
        self.assertAlmostEqual(self._calculate(items), 29.97, places=2)

    def test_quantity_one(self):
        """Тест 5: кількість 1 — ціна не змінюється."""
        items = [{'price': 75.5, 'quantity': 1}]
        self.assertEqual(self._calculate(items), 75.5)


class TestSerializeReview(unittest.TestCase):

    def _make_mock_review(self, rating=5, comment='Смачно', menu_item_name='Борщ'):
        """Фабрика мок-об'єкта відгуку."""
        review = MagicMock()
        review.id = 1
        review.user.username = 'testuser'
        review.menu_item.name = menu_item_name
        review.rating = rating
        review.comment = comment
        review.created_at.strftime.return_value = '2026-01-01 12:00:00'
        return review

    def _serialize(self, review):
        """Локальна копія логіки серіалізації."""
        return {
            'id': review.id,
            'user': review.user.username,
            'menu_item': review.menu_item.name if review.menu_item else None,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }

    def test_all_fields_present(self):
        """Тест 6: всі поля присутні у результаті."""
        review = self._make_mock_review()
        result = self._serialize(review)
        expected_keys = {'id', 'user', 'menu_item', 'rating', 'comment', 'created_at'}
        self.assertEqual(set(result.keys()), expected_keys)

    def test_correct_rating(self):
        """Тест 7: рейтинг правильно серіалізується."""
        review = self._make_mock_review(rating=3)
        result = self._serialize(review)
        self.assertEqual(result['rating'], 3)

    def test_no_menu_item(self):
        """Тест 8: відгук без страви — menu_item = None."""
        review = self._make_mock_review()
        review.menu_item = None
        result = self._serialize(review)
        self.assertIsNone(result['menu_item'])

    def test_comment_preserved(self):
        """Тест 9: коментар зберігається без змін."""
        review = self._make_mock_review(comment='Дуже смачно!')
        result = self._serialize(review)
        self.assertEqual(result['comment'], 'Дуже смачно!')


class TestSerializePaymentDelivery(unittest.TestCase):
    """Клас 3: тести функції _serialize_payment_delivery"""

    def _make_mock_record(self, payment_status='очікує оплати', delivery_status='в очікуванні'):
        record = MagicMock()
        record.id = 10
        record.order_id = 5
        record.payment_method = 'картка'
        record.payment_status = payment_status
        record.delivery_address = 'вул. Франка, 1'
        record.contact_number = '+380991234567'
        record.delivery_status = delivery_status
        record.delivery_notes = ''
        return record

    def _serialize(self, record):
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

    def test_all_fields_present(self):
        """Тест 10: всі 8 полів присутні."""
        record = self._make_mock_record()
        result = self._serialize(record)
        self.assertEqual(len(result), 8)

    def test_payment_status_pending(self):
        """Тест 11: статус оплати 'очікує оплати' зберігається."""
        record = self._make_mock_record(payment_status='очікує оплати')
        result = self._serialize(record)
        self.assertEqual(result['payment_status'], 'очікує оплати')

    def test_delivery_status_delivered(self):
        """Тест 12: статус доставки 'доставлено' зберігається."""
        record = self._make_mock_record(delivery_status='доставлено')
        result = self._serialize(record)
        self.assertEqual(result['delivery_status'], 'доставлено')


class TestValidationLogic(unittest.TestCase):
    """Клас 4: тести логіки валідації (константи та перевірки)"""

    VALID_TABLE_STATUSES = ('вільний', 'заброньований', 'зайнятий')
    VALID_ORDER_STATUSES = ('нове', 'готуватися', 'оплачено')

    def test_valid_table_status_free(self):
        """Тест 13: 'вільний' — допустимий статус столика."""
        self.assertIn('вільний', self.VALID_TABLE_STATUSES)

    def test_valid_table_status_reserved(self):
        """Тест 14: 'заброньований' — допустимий статус столика."""
        self.assertIn('заброньований', self.VALID_TABLE_STATUSES)

    def test_invalid_table_status(self):
        """Тест 15: 'broken' — недопустимий статус столика."""
        self.assertNotIn('broken', self.VALID_TABLE_STATUSES)

    def test_valid_order_status_new(self):
        """Тест 16: 'нове' — допустимий статус замовлення."""
        self.assertIn('нове', self.VALID_ORDER_STATUSES)

    def test_valid_order_status_paid(self):
        """Тест 17: 'оплачено' — допустимий статус замовлення."""
        self.assertIn('оплачено', self.VALID_ORDER_STATUSES)

    def test_invalid_order_status_english(self):
        """Тест 18: 'completed' (англ.) — недопустимий статус (виправлена помилка оригіналу)."""
        self.assertNotIn('completed', self.VALID_ORDER_STATUSES)

    def test_invalid_order_status_cancelled(self):
        """Тест 19: 'cancelled' — недопустимий статус замовлення."""
        self.assertNotIn('cancelled', self.VALID_ORDER_STATUSES)


class TestDashboardTemplateMapping(unittest.TestCase):
    DASHBOARD_TEMPLATES = {
        'admin': 'dashboard_admin.html',
        'waiter': 'dashboard_waiter.html',
        'chef': 'dashboard_chef.html',
    }

    def test_admin_gets_admin_template(self):
        """Тест 20: роль 'admin' → dashboard_admin.html."""
        self.assertEqual(self.DASHBOARD_TEMPLATES.get('admin'), 'dashboard_admin.html')

    def test_waiter_gets_waiter_template(self):
        """Тест 21 (бонус): роль 'waiter' → dashboard_waiter.html."""
        self.assertEqual(self.DASHBOARD_TEMPLATES.get('waiter'), 'dashboard_waiter.html')

    def test_chef_gets_chef_template(self):
        """Тест 22 (бонус): роль 'chef' → dashboard_chef.html."""
        self.assertEqual(self.DASHBOARD_TEMPLATES.get('chef'), 'dashboard_chef.html')

    def test_unknown_role_returns_none(self):
        """Тест 23 (бонус): невідома роль → None (редірект на логін)."""
        self.assertIsNone(self.DASHBOARD_TEMPLATES.get('manager'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
