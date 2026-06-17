from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'lotes_expf7_secret'

# --- BANCO DE DADOS ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Lote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_geracao = db.Column(db.DateTime)
    programa_doc = db.Column(db.String(100))
    produto = db.Column(db.String(100))
    cor_n = db.Column(db.String(100))
    numero_calcado = db.Column(db.String(20))
    motivo_retencao = db.Column(db.String(200))
    turno = db.Column(db.String(50))
    status_revisao = db.Column(db.String(20), default='Pendente')
    quem_revisou = db.Column(db.String(100))
    data_revisao = db.Column(db.DateTime)
    qtd_problemas = db.Column(db.Integer, default=0)
    obs_tecnica = db.Column(db.Text)
    email_respondido = db.Column(db.String(10), default='Não')
    quem_respondeu = db.Column(db.String(100))
    data_resposta = db.Column(db.DateTime)

with app.app_context():
    db.create_all()

# --- AUXILIAR ---
def calcular_turno(hora_atual):
    hora = hora_atual.strftime('%H:%M')
    if '06:00' <= hora <= '14:48': return "1º Turno"
    elif '14:50' <= hora <= '23:40': return "2º Turno"
    return "3º Turno"

# --- ROTAS ---

@app.route("/")
def index():
    total = Lote.query.count()
    revisados = Lote.query.filter_by(status_revisao='Revisado').count()
    lotes = Lote.query.all()
    
    no_prazo_count = 0
    agora = datetime.now()
    for lote in lotes:
        prazo = lote.data_geracao + timedelta(hours=24)
        if agora <= prazo:
            no_prazo_count += 1
            
    stats = {
        "total": total,
        "revisados": revisados,
        "no_prazo": no_prazo_count,
        "atrasados": total - no_prazo_count,
        "perc_prazo": round((revisados / total * 100), 1) if total > 0 else 0
    }
    return render_template("index.html", stats=stats)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_digitado = request.form.get('username')
        password_digitado = request.form.get('password')
        if username_digitado == 'admin' and password_digitado == '123':
            session['logged_in'] = True
            session['usuario_nome'] = username_digitado.capitalize()
            return redirect(url_for('dashboard_interno'))
        return render_template("login.html", erro="Senha incorreta")
    return render_template("login.html")

@app.route("/dashboard_interno")
def dashboard_interno():
    pendentes = Lote.query.filter_by(status_revisao='Pendente').count()
    lotes_pendentes = Lote.query.filter_by(status_revisao='Pendente').all()
    no_prazo = 0
    agora = datetime.now()
    for l in lotes_pendentes:
        if agora <= (l.data_geracao + timedelta(hours=24)):
            no_prazo += 1

    stats = {
        "no_prazo": no_prazo,
        "fora_prazo": pendentes - no_prazo,
        "aguardando": pendentes
    }
    return render_template("dashboard_interno.html", stats=stats)

@app.route("/novo_lote", methods=["GET", "POST"])
def novo_lote():
    if request.method == "POST":
        novo = Lote(
            data_geracao = datetime.strptime(request.form.get('data'), '%Y-%m-%d'),
            programa_doc = request.form.get('programa_doc'),
            produto = request.form.get('produto'),
            cor_n = request.form.get('cor'),
            numero_calcado = request.form.get('numero'),
            motivo_retencao = request.form.get('motivo'),
            turno = request.form.get('turno')
        )
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('dashboard_interno'))
    agora = datetime.now()
    return render_template("novo_lote.html", data_hoje=agora.strftime('%Y-%m-%d'), turno=calcular_turno(agora))

@app.route("/relatorio")
def relatorio():
    lotes = Lote.query.all() 
    return render_template("relatorio.html", lotes=lotes)

@app.route("/detalhe_lote/<int:id>")
def detalhe_lote_pagina(id):
    lote = Lote.query.get_or_404(id)
    return render_template("detalhe_lote.html", lote=lote)

# Rota para confirmar APENAS o e-mail
@app.route("/confirmar_email/<int:id>", methods=["POST"])
def confirmar_email_acao(id):
    lote = Lote.query.get_or_404(id)
    lote.quem_respondeu = request.form.get("quem_respondeu")
    db.session.commit()
    return redirect(url_for('detalhe_lote_pagina', id=id))

@app.route("/excluir_lote/<int:id>", methods=["POST"])
def excluir_lote(id):
    lote = Lote.query.get_or_404(id)
    db.session.delete(lote)
    db.session.commit()
    return redirect(url_for('relatorio'))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))

from datetime import datetime

# Rota para abrir a página de busca de revisão
@app.route('/concluir_revisao')
def concluir_revisao_busca():
    doc = request.args.get('doc')
    num = request.args.get('num')
    lote = None
    
    if doc and num:
        lote = Lote.query.filter_by(programa_doc=doc, numero_calcado=num).first()
    
    hoje = datetime.now().strftime('%Y-%m-%d')
    return render_template('concluir_revisao.html', 
                           lote=lote, 
                           doc_buscado=doc, 
                           num_buscado=num, 
                           data_hoje=hoje)

# Rota para salvar a revisão no banco de dados
@app.route("/finalizar_revisao_db/<int:id>", methods=["POST"])
def finalizar_revisao_db(id):
    lote = Lote.query.get_or_404(id)
    
    status_abastecido = request.form.get('status_abastecido')
    data_rev_str = request.form.get('data_revisao')
    
    lote.data_revisao = datetime.strptime(data_rev_str, '%Y-%m-%d')
    
    if status_abastecido == 'SIM':
        lote.status_revisao = 'Abastecido'
        lote.quem_revisou = request.form.get('quem_revisou') or "N/A"
        lote.qtd_problemas = int(request.form.get('qtd_problemas') or 0)
    else:
        lote.status_revisao = 'Revisado'
        lote.quem_revisou = request.form.get('quem_revisou')
        lote.qtd_problemas = int(request.form.get('qtd_problemas') or 0)

    db.session.commit()
    return redirect(url_for('relatorio'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
