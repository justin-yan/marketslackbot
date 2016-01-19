What operations should the marketslackbot support?

bid 1.1
bid 1.1 for 5
ask 1.1
ask 1.1 for 4
hit 5
lift 4

start <descrip> // launch a new book with <descrip>
settle <price>  // settle current market at <price>
mypos  // view your current positions
mybook // view your current orders
clear  // removes all of your orders
book   // view entire market book and description

New bids and orders should insert quickly.
Find/pop min/max should also be fast (will need to check for crossing on every bid/ask).

Two linked lists (one each for bids and asks) are actually a pretty reasonable way of doing this, since most price action should take place near the spread, which means you won't have to iterate through the list all that frequently.

settle, mypos, clear, and book will all require a full traversal through both LLs.

class Market:
    self.description::String
    self.book = Book
    self.position_book::Dict[user_id, Position]

class Book:
    self.bids = OrderChain
    self.offers = OrderChain

class OrderChain:
    self.head = Order

class Order:
    self.next = Option(Order)
    self.owner = <user_id>

class Position:
    self.cash
    self.net_long

An associative array to hold a 1:1 channel<->market association...?