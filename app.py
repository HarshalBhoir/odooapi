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
    conn = psycopg2.connect("dbname='production' user='openerp' host='localhost' password='password'")
    cr = conn.cursor()
except:
    print "I am unable to connect to the database"

@app.route('/')
def index():
    return "Api's to export data from odoo"

@app.route('/todo/api/v1.0/tasks', methods=['GET'])
def get_tasks():
    return jsonify({'tasks': tasks})

@app.route('/export/partners', methods=['GET'])
def get_partners():
    # Get partners
    sql = '''
	SELECT array_to_json(array_agg(row_to_json(t)))
	FROM (
	SELECT
        id,
	part.name,
        ref as reference,
        customer as is_customer,
        supplier as is_supplier,
	credit_limit,
	active,
	vat as vat_number,
        comment as notes,
        sale_warn,
        sale_warn_msg,
        invoice_warn,
        invoice_warn_msg,
	(
	     SELECT row_to_json(d)
	     FROM (
		     SELECT payment_id as id, term.name
		     FROM (SELECT split_part(res_id, ',', 2)::int AS partner_id,split_part(value_reference, ',', 2)::int AS payment_id 
			   FROM ir_property
			   WHERE name = 'property_payment_term' AND fields_id=1363) AS payment_term 
		     LEFT JOIN account_payment_term term ON (term.id = payment_term.payment_id)
		     WHERE partner_id = part.id
		) as d
	) as payment_term,
        (
        SELECT array_to_json(array_agg(row_to_json(d)))
        FROM (
                SELECT add.id, type, street, street2, zip as zipcode, city, state.name as state,
		       phone, mobile, email, fax, add.name,
		       row_to_json(country) as country
                FROM res_partner_address add
		LEFT JOIN res_country_state state on (state.id = add.state_id)
                LEFT JOIN (SELECT id, code, name from res_country) country
			on (country.id = add.country_id)
                WHERE add.partner_id = part.id
		and add.name is not null
        ) d
        ) as address,
	coalesce(pricelist.sale_pricelist_id, 1) as sale_pricelist_id,
	(SELECT row_to_json(d)
		FROM (
		SELECT id, name
		   FROM res_users
		 WHERE id = part.user_id
	) as d
	) as sales_person
	FROM res_partner part
	LEFT JOIN(
		SELECT split_part(res_id, ',', 2)::int AS partner_id,split_part(value_reference, ',', 2)::int AS sale_pricelist_id 
		FROM ir_property
		WHERE name = 'property_product_pricelist' AND fields_id=950) as pricelist on (pricelist.partner_id = part.id)
	) t
	'''
    cr.execute(sql)
    partners = cr.fetchone()
    return jsonify({'data': partners and partners[0]})

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

@app.route('/export/pricelists', methods=['GET'])
def get_pricelists():
    sql = '''
SELECT array_to_json(array_agg(row_to_json(t)))
FROM (
SELECT
	pricelist.id,
	pricelist.name,
	pricelist.active,
	(
		SELECT row_to_json(d)
		FROM (
			SELECT id, name FROM res_currency
			WHERE id=pricelist.currency_id) as d
	) as currency,
	(
		SELECT array_to_json(array_agg(row_to_json(d)))
		FROM (
			SELECT item.id,
				   item.name,
				   item.product_id,
				   item.categ_id,
				   item.sequence,
				   item.min_quantity,
				   item.base,
				   item.base_pricelist_id,
				   item.price_discount,
				   item.price_surcharge,
				   item.price_round,
				   item.price_min_margin,
				   item.price_max_margin
				   FROM product_pricelist_version version
			LEFT JOIN product_pricelist_item AS item ON
				(item.price_version_id = version.id)
			WHERE version.pricelist_id = pricelist.id ) AS d
	) as rules
FROM
	product_pricelist pricelist
) AS t
'''
    cr.execute(sql)
    priceslists = cr.fetchone()
    return jsonify({'data': priceslists and priceslists[0]})


@app.route('/export/sales', methods=['GET'])
def get_sales():
    sql = '''
	SELECT row_to_json(t)
	FROM (
	SELECT
		CASE WHEN inv.type='out_invoice' THEN 'Sale'
		ELSE 'Refund'
		END AS type,
		inv.date_invoice,
		inv.partner_id,
		line.product_id,
		line.quantity AS qty,
		line.price_subtotal AS amount,
		coalesce(product.standard_price, 0.0) AS cost_price,
		line.price_subtotal - (product.standard_price * line.quantity) AS margin
	FROM account_invoice inv
	LEFT JOIN account_invoice_line line
		ON (line.invoice_id = inv.id)
	LEFT JOIN (SELECT prod.id, templ.standard_price FROM product_product prod
		LEFT JOIN product_template templ ON (prod.product_tmpl_id = templ.id)) product ON (product.id = line.product_id)
	WHERE
		inv.type IN ('out_invoice', 'out_refund')
		AND inv.state not in ('draft', 'cancel')
	) t
'''
    cr.execute(sql)
    sales = cr.fetchall()
    return jsonify({'data': sales})


@app.route('/export/products', methods=['GET'])
def get_products():
    #sql = ''' select array_to_json(array_agg(row_to_json(t)))
    #from (
    #  select id, name from product_template order by id
    #) t '''
    sql = ''' 
	SELECT  array_to_json(array_agg(row_to_json(t))) from (
SELECT prod.id,
       prod.active,
       prod.default_code,
       tmpl.name,
       prod.ean13,
       tmpl.volume,
       tmpl.weight_net as weight,
       tmpl.type, -- use if else to fill in product type string
       (
	SELECT array_to_json(array_agg(row_to_json(d)))
	FROM (
	     	SELECT lines.product_id, lines.product_qty as qty, lines.name
		FROM mrp_bom bom
		LEFT JOIN mrp_bom lines ON (bom.id = lines.bom_id)
		WHERE bom.product_id = prod.id
	) d
 	) as components,
       (
        SELECT row_to_json(d)
        FROM (
             SELECT id, name
                FROM product_category
                WHERE id = tmpl.categ_id
        ) d
       ) as category,
       tmpl.supply_method,
       tmpl.list_price as sale_price,
       tmpl.standard_price as cost_price,
       tmpl.description,
       (
        SELECT array_to_json(array_agg(row_to_json(d)))
        FROM (
                SELECT tax.id, tax.description as code, amount as rate, name
                     FROM product_taxes_rel prod_stax
                     INNER JOIN account_tax tax on (tax.id = prod_stax.tax_id)
                     where prod_stax.prod_id = prod.id
        ) d
        ) as sale_tax,
       (
        SELECT array_to_json(array_agg(row_to_json(d)))
        FROM (
                SELECT tax.id, tax.description as code, amount as rate, name
                     FROM product_supplier_taxes_rel prod_ptax
                     INNER JOIN account_tax tax on (tax.id = prod_ptax.tax_id)
                     where prod_ptax.prod_id = prod.id
        ) d
        ) as purchase_tax,
       (
        SELECT row_to_json(d)
        FROM (
             SELECT id, name
                FROM product_uom
                WHERE id = tmpl.uom_id
        ) d
       ) as uom,
       (
        SELECT array_to_json(array_agg(row_to_json(d)))
        FROM (
             SELECT sup.id, delay as delivery_lead_time, min_qty, row_to_json(part) as partner
                FROM product_supplierinfo sup
                LEFT JOIN (SELECT id, name from res_partner) part on (part.id = sup.name)
                WHERE sup.product_id = prod.id
        ) d
       ) as suppplier,
       (
	SELECT row_to_json(d) FROM (
             SELECT COALESCE((sin.qty - sout.qty),0) AS qty_onhand,
	            COALESCE((sin.qty - sout.qty - soutgoing.qty),0) AS qty_available, 
        COALESCE(swo.product_max_qty,0) AS qty_rule_max, 
        COALESCE(swo.product_min_qty,0) AS qty_rule_min 
       FROM   product_product product
       LEFT JOIN (SELECT Sum(product_qty) AS qty, 
                         product_id 
                  FROM   stock_move 
                  WHERE  location_id NOT IN ( 12 ) 
                         AND location_dest_id IN ( 12 ) 
                         AND state IN ( 'done' ) 
                  GROUP  BY product_id) AS sin 
              ON ( sin.product_id = product.id ) 
       LEFT JOIN (SELECT Sum(product_qty) AS qty, 
                         product_id 
                  FROM   stock_move 
                  WHERE  location_id IN ( 12 ) 
                         AND location_dest_id NOT IN ( 12 ) 
                         AND state IN ( 'done' ) 
                  GROUP  BY product_id) AS sout 
              ON ( sout.product_id = product.id ) 
       LEFT JOIN (SELECT Sum(product_qty) AS qty, 
                         product_id 
                  FROM   stock_move 
                  WHERE  location_id IN ( 12 ) 
                         AND location_dest_id NOT IN ( 12 ) 
                         AND state IN ( 'waiting', 'confirmed', 'assigned' ) 
                  GROUP  BY product_id) AS soutgoing 
              ON ( soutgoing.product_id = product.id ) 
       LEFT JOIN stock_warehouse_orderpoint swo 
              ON ( swo.product_id = product.id ) 
WHERE  prod.id = product.id
) d ) as stock 

FROM product_product prod
LEFT JOIN product_template tmpl
        ON (tmpl.id = prod.product_tmpl_id)
) t
	'''
    cr.execute(sql)
    products = cr.fetchone()
    return jsonify({'data': products and products[0]})

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
