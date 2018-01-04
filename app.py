import psycopg2
from flask import Flask, jsonify, make_response

app = Flask(__name__)


test_tasks = [
    {
        'id': 1,
        'title': u'Buy groceries',
        'description': u'Milk, Cheese, Pizza, Fruit, Tylenol',
        'done': False
    },
    {
        'id': 2,
        'title': u'Learn Python',
        'description': u'Need to find a good Python tutorial on the web',
        'done': False
    }
]

try:
    conn = psycopg2.connect("dbname='odoo_test' user='postgres' host='127.0.0.1' password='postgres'")
    cr = conn.cursor()
except:
    print "I am unable to connect to the database"

@app.route('/')
def index():
    return "Api's to export data from odoo"

@app.route('/todo/api/v1.0/tasks', methods=['GET'])
def get_tasks():
    return jsonify({'tasks': tasks})

@app.route('/export/categories', methods=['GET'])
def get_categories():
    # Call Category view from postgresql
    sql = ''' select array_to_json(array_agg(row_to_json(t)))
    from (
      select id, parent_id, name from product_category order by id
    ) t '''
    cr.execute(sql)
    categories = cr.fetchone()
    return jsonify({'data': categories and categories[0]})

@app.route('/export/products', methods=['GET'])
def get_products():
    sql = ''' select array_to_json(array_agg(row_to_json(t)))
    from (
      select id, name from product_product order by id
    ) t '''
    cr.execute(sql)
    products = cr.fetchone()
    return jsonify({'data': products})

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

if __name__ == '__main__':
    app.run(debug=True)
