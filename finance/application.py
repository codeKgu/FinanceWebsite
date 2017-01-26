from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
import os

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

app.secret_key = os.urandom(24)

@app.route("/")
@login_required
def index():
    rows_portfolio = db.execute("SELECT symbol, company, SUM(shares) AS shares FROM portfolio WHERE id = :id GROUP BY company", id = session["user_id"])
    total = 0
    for row in range(len(rows_portfolio)):
        rows_portfolio[row]["price"] = usd(lookup(rows_portfolio[row]["symbol"])["price"])
        rows_portfolio[row]["total"] = usd(lookup(rows_portfolio[row]["symbol"])["price"] * rows_portfolio[row]["shares"])
        total += lookup(rows_portfolio[row]["symbol"])["price"] * rows_portfolio[row]["shares"] 
        
    #deletes rows in rows_portfolio if there are 0 shares for that company
    new_row = []
    for row in range(len(rows_portfolio)):
        if  rows_portfolio[row]["shares"] != 0:
            new_row.append(rows_portfolio[row])
    
    user = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
    cash = user[0]["cash"]
    total += cash
    total = usd(total)
    cash = usd(cash)
    return render_template("index.html", portfolio = new_row, cash = cash, total = total)
     

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        #ensures proper usage
        symbol = request.form.get("symbol")
        if symbol == "":
            return apology("Please Enter a Symbol")
        elif lookup (symbol) == None:
            return apology("Sorry stock not found")
        elif request.form.get("shares") == None:
            return apology("Please Enter Number of Shares")
        elif RepresentsInt(request.form.get("shares")) == False:
            return apology("Invalid input")
        elif int(request.form.get("shares")) <= 0:
            return apology("Please enter a positive number")
        else: 
            row = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
            cash = row[0]["cash"]
            price = lookup(request.form.get("symbol"))["price"]
            company = lookup(request.form.get("symbol"))["name"]
            shares = int(request.form.get("shares"))
            symbol = lookup(symbol)["symbol"]
            if shares * price <= cash:
                db.execute("INSERT INTO portfolio (id, company, price, shares, symbol) VALUES (:id, :company, :price, :shares, :symbol )", id = session["user_id"], company = company, price = price, shares = shares, symbol = symbol)
                cash -= price * shares
                db.execute("UPDATE users SET cash =:cash WHERE id = :id", cash = cash, id = session["user_id"])
                return redirect(url_for("index"))
            else:
                return apology ("Not enough money in your account")
                
    return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    rows_history = db.execute("SELECT symbol, time_stamp, shares, price   FROM portfolio WHERE id = :id ORDER BY time_stamp DESC", id = session["user_id"])
    #if shares in database is negative it is sold, otherwise it is bought
    #changes shares that are negative from database to positive for display
    
    for row in range(len(rows_history)):
        rows_history[row]["price"] = usd(rows_history[row]["price"])
        if rows_history[row]["shares"] < 0:
            rows_history[row]["action"] = "Sold"
            rows_history[row]["shares"] = abs(rows_history[row]["shares"])
        else:
            rows_history[row]["action"] = "Bought"
        
    return render_template("history.html", history = rows_history)
    
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if request.form.get("symbol") == "":
            return apology("Please Enter a Symbol")
        elif lookup (request.form.get("symbol")) == None:
            return apology("Sorry stock not found")
        else:
            company = lookup(request.form.get("symbol"))["name"]
            price = usd (lookup(request.form.get("symbol"))["price"])
            symbol = lookup(request.form.get("symbol"))["symbol"]
            return render_template("quoted.html", company = company, price =price, symbol = symbol)
    
    return render_template("quote.html")
    return apology("TODO")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    session.clear()
    if request.method == "POST":
        if request.form.get("username") == "":
            return apology("Please enter a username")
        elif request.form.get("password") =="":
            return apology("Please enter a password")
        elif request.form.get("confirm_password") =="":
            return apology("Please enter a confirmation password")
        elif request.form.get("confirm_password") != request.form.get("password"):
            return apology("Passwords don't match")
        else:
            hash = pwd_context.hash(request.form.get("password"))
            result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username = request.form.get("username"), hash =hash)
            if not result:
                return apology ("User already registered")
            
            row = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
            session ["user_id"] = row[0]["id"]
        
        return redirect(url_for("index"))
    
    else:
        return render_template("register.html")
   

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if symbol == "":
            return apology("Please Enter a Symbol")
        elif lookup (symbol) == None:
            return apology("Sorry stock not found")
        elif request.form.get("shares") == "":
            return apology("Please Enter Number of Shares")
        elif RepresentsInt(request.form.get("shares")) == False:
            return apology("Invalid input")
        elif int(request.form.get("shares")) <= 0:
            return apology("Please enter a positive number")
        else: 
            portfolio = db.execute("SELECT symbol, company, SUM(shares) AS shares FROM portfolio WHERE id = :id GROUP BY symbol", id = session["user_id"])
            user = db.execute("SELECT * FROM users WHERE id = :id ", id = session["user_id"])
            symbol = lookup(symbol)["symbol"]
            shares = int(request.form.get("shares"))
            for row in range(len(portfolio)):
                if symbol == portfolio[row]["symbol"]:
                    if shares <= portfolio[row]["shares"]:
                        cost = shares * lookup(symbol)["price"]
                        total = user[0]["cash"] + cost
                        company = lookup(symbol)["name"]
                        shares = -shares
                        price = lookup(symbol)["price"]
                        db.execute("UPDATE users SET cash= :cash WHERE id =:id", cash =total, id = session["user_id"])
                        db.execute("INSERT INTO portfolio (id, company, price, shares, symbol) VALUES (:id, :company, :price, :shares, :symbol )", id = session["user_id"], company = company, price = price, shares = shares, symbol = symbol)
                        return redirect(url_for("index"))
                        
                    else:
                        return apology("You do not have enough shares")
                else:
                    continue
        return apology ("You do not have these shares")
    return render_template("sell.html")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """adds money to user account"""
    if request.method == "POST":
        if request.form.get("amount") == "":
            return apology("Please enter amount")
        elif representsFloat(request.form.get("amount")) == False:
            return apology("Invalid Input")
        elif float(request.form.get("amount")) <= 0:
            return apology("Please enter a positive amount")
        else:
            user = db.execute("SELECT* FROM users WHERE id =:id ", id= session["user_id"])
            cash = float(request.form.get("amount")) + user[0]["cash"]
            db.execute("UPDATE users SET cash = :cash WHERE id=:id", cash = cash, id = session["user_id"])
            return redirect(url_for("index"))
    
    return render_template("deposit.html")
