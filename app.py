from http import HTTPStatus

from flask import Flask, jsonify, request, g
from random import choice
from pathlib import Path

import sqlite3

BASE_DIR = Path(__file__).parent
path_to_db = BASE_DIR / "store.db"  # <- путь к БД

app = Flask(__name__)

app.json.ensure_ascii = False

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(path_to_db)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/quotes/", defaults={'num': None})
@app.route("/quotes/<int:num>")
def get_quote(num:int):
    keys = ('id', 'author', 'text', 'rating')
    cursor = get_db().cursor()
    if num or num == 0:
        res = cursor.execute("SELECT * FROM quotes WHERE id = ?", (num,)).fetchone()
        if res:
            return jsonify(dict(zip(keys, res))), 200
        return {'Error': f'Quote with id={num} not found'}, 404

    cursor.execute("SELECT * FROM quotes")
    res = cursor.fetchall()
    qts = []
    for res in res:
        qts.append(dict(zip(keys, res)))
    return jsonify(qts), 200

@app.route("/quotes/count")
def quotes_count():
    return  jsonify({'count': get_db().cursor().execute("SELECT count(*) as count FROM quotes").fetchone()[0]}), 200

@app.route("/quotes/random")
def quotes_random():
    res = get_db().cursor().execute("SELECT id FROM quotes").fetchall()
    return get_quote((choice(res))[0]) if res else jsonify({'Message': 'Response is empty.'})

@app.route("/quotes", methods=['POST'])
def create_quote():
    data = request.json

    if not data:
        return {'error': 'No valid data to update'}, 400

    auth_req = data.get("author")
    txt_req = data.get("text")
    rtg_reg = data.get("rating")

    if auth_req and txt_req and rtg_reg:

        if rtg_reg not in range(1, 6):
            return {"error": "Rating must be between 1 and 5"}, 400

        try:
            cursor = get_db().cursor()
            num = cursor.execute("INSERT INTO quotes (author,text,rating) VALUES (?, ?, ?)", (auth_req, txt_req, rtg_reg)).lastrowid
            get_db().commit()
            return jsonify({'id': num, 'author': auth_req, 'text': txt_req, 'rating': rtg_reg}), 201
        except Exception as e:
            return jsonify({'Error': str(e)}), 400

    return {"error": "No valid data to update. Required: <author>, <text>, <rating>. Rating must be between 1 and 5"}, 400

@app.route("/quotes/", methods=['DELETE'], defaults={'num': None})
@app.route("/quotes/<int:num>", methods=['DELETE'])
def delete_quote(num:int):
    if num or num == 0:
        try:
            cursor = get_db().cursor()
            val = cursor.execute(f"DELETE FROM quotes WHERE id = ?", (num,)).rowcount
            get_db().commit()
            if val >0:
                return jsonify({'Message': f'Quote whit id={num} was deleted.'}), 200
            elif val == 0:
                return {'Error': "DELETE operation failed."}, 400
        except Exception as e:
            return {'Error': str(e)}, 400

    else:
        return jsonify({'Error': 'The request is empty.'}), 400

@app.route('/quotes/<int:quote_id>', methods=['PUT'])
def edit_quote(quote_id):
    new_data = request.json
    if not new_data:
        return {'error': 'No valid data to update'}, 400

    attributes: set = set(new_data.keys()) & {"author", "text", "rating"}
    if 'rating' in attributes and new_data['rating'] not in range(1, 6):
        attributes.remove('rating')
    if not attributes:
        return {"error": "No valid data to update. The request cannot be empty. Rating must be between 1 and 5"}, 400

    resp, status_code = get_quote(quote_id)
    if status_code != 200:
        return {'error': f'Quote with id={quote_id} not found'}, 404

    update_quotes = f"UPDATE quotes SET {', '.join(attr + '=?' for attr in attributes)} WHERE id=?"
    params = tuple(new_data.get(attr) for attr in attributes)+ (quote_id,)
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute(update_quotes, params)
    rows = cursor.rowcount

    if rows:
        connection.commit()
        cursor.close()

    resp, status_code = get_quote(quote_id)

    return resp, status_code


if __name__ == "__main__":
    app.run(debug=True)
