
import grpc.aio
import uuid
import os
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Import the generated gRPC files
from . import demo_pb2
from . import demo_pb2_grpc

# --- Agent State ---
user_id = None
order_tracking_db = {}

# --- Tool Implementations ---
def set_user_id(new_user_id: str) -> dict:
    """Sets the user ID for the current session."""
    global user_id
    user_id = new_user_id
    return {"status": "success", "report": f"User ID has been set to {user_id}."}

async def add_item_to_cart(product_name: str, quantity: int) -> dict:
    """Adds a specified quantity of a product to the shopping cart and suggests recommended items."""
    if not user_id:
        return {"status": "error", "error_message": "User ID is not set."}
    
    product_id = None
    try:
        async with grpc.aio.insecure_channel('localhost:3550') as channel:
            stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
            search_request = demo_pb2.SearchProductsRequest(query=product_name)
            search_response = await stub.SearchProducts(search_request)
            if len(search_response.results) != 1:
                return {"status": "error", "error_message": f"Could not find a unique product: '{product_name}'."}
            product_id = search_response.results[0].id
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Error searching for product: {e.details()}"}

    try:
        async with grpc.aio.insecure_channel('localhost:7070') as channel:
            stub = demo_pb2_grpc.CartServiceStub(channel)
            request = demo_pb2.AddItemRequest(user_id=user_id, item=demo_pb2.CartItem(product_id=product_id, quantity=quantity))
            await stub.AddItem(request)
            base_report = f"Successfully added {quantity} of {product_name} to your cart."
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Error adding item to cart: {e.details()}"}

    if product_name.lower() == 'sunglasses':
        recommendations = ["Tank Top", "Watch"]
        recommendation_report = f" I also recommend: {', '.join(recommendations)}. Would you like to add any?"
        return {"status": "success", "report": base_report + recommendation_report}

    return {"status": "success", "report": base_report}

async def get_cart() -> dict:
    """Retrieves the current contents of the shopping cart."""
    if not user_id:
        return {"status": "error", "error_message": "User ID is not set."}
    try:
        async with grpc.aio.insecure_channel('localhost:7070') as cart_channel:
            cart_stub = demo_pb2_grpc.CartServiceStub(cart_channel)
            cart_request = demo_pb2.GetCartRequest(user_id=user_id)
            cart_response = await cart_stub.GetCart(cart_request)
            if not cart_response.items:
                return {"status": "success", "report": "Your shopping cart is empty."}
            items_with_names = []
            async with grpc.aio.insecure_channel('localhost:3550') as catalog_channel:
                catalog_stub = demo_pb2_grpc.ProductCatalogServiceStub(catalog_channel)
                for item in cart_response.items:
                    product_request = demo_pb2.GetProductRequest(id=item.product_id)
                    product = await catalog_stub.GetProduct(product_request)
                    items_with_names.append(f"{item.quantity} x {product.name}")
            report = "Your cart contains: " + ", ".join(items_with_names)
            return {"status": "success", "report": report}
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Error getting cart contents: {e.details()}"}

async def empty_cart() -> dict:
    """Removes all items from the current user's shopping cart."""
    if not user_id:
        return {"status": "error", "error_message": "User ID is not set."}
    try:
        async with grpc.aio.insecure_channel('localhost:7070') as channel:
            stub = demo_pb2_grpc.CartServiceStub(channel)
            request = demo_pb2.EmptyCartRequest(user_id=user_id)
            await stub.EmptyCart(request)
            return {"status": "success", "report": "Your shopping cart has been emptied."}
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Error emptying cart: {e.details()}"}

async def place_order(email: str, street_address: str, city: str, state: str, zip_code: str, country: str, credit_card_number: str, credit_card_cvv: int, credit_card_expiration_year: int, credit_card_expiration_month: int) -> dict:
    """Places the order with the items currently in the cart."""
    if not user_id:
        return {"status": "error", "error_message": "User ID is not set."}
    
    try:
        script_dir = os.path.dirname(__file__)
        fraud_file_path = os.path.join(script_dir, 'fraudulent_cards.txt')
        with open(fraud_file_path, 'r') as f:
            fraudulent_cards = [line.strip() for line in f]
        if credit_card_number in fraudulent_cards:
            return {"status": "error", "error_message": "Possible fraud detected."}
    except FileNotFoundError:
        pass

    try:
        async with grpc.aio.insecure_channel('localhost:5050') as channel:
            stub = demo_pb2_grpc.CheckoutServiceStub(channel)
            request = demo_pb2.PlaceOrderRequest(
                user_id=user_id, user_currency="USD", email=email,
                address=demo_pb2.Address(street_address=street_address, city=city, state=state, zip_code=int(zip_code), country=country),
                credit_card=demo_pb2.CreditCardInfo(credit_card_number=credit_card_number, credit_card_cvv=credit_card_cvv, credit_card_expiration_year=credit_card_expiration_year, credit_card_expiration_month=credit_card_expiration_month)
            )
            response = await stub.PlaceOrder(request)
            order_id = response.order.order_id
            tracking_id = response.order.shipping_tracking_id
            order_tracking_db[order_id] = tracking_id
            return {"status": "success", "report": f"Order placed successfully! Your order ID is {order_id}."}
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Error placing order: {e.details()}"}

async def track_order(order_id: str) -> dict:
    """Looks up the shipping tracking ID for a given order ID."""
    if order_id in order_tracking_db:
        tracking_id = order_tracking_db[order_id]
        return {"status": "continue", "next_tool": "get_package_status", "arguments": {"tracking_id": tracking_id}}
    else:
        return {"status": "error", "error_message": f"Order ID '{order_id}' not found."}

async def list_products() -> dict:
    """Retrieves the list of all products from the Online Boutique."""
    try:
        async with grpc.aio.insecure_channel('localhost:3550') as channel:
            stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
            response = await stub.ListProducts(demo_pb2.Empty())
            product_info = [f"{p.name} (ID: {p.id})" for p in response.products]
            return {"status": "success", "report": "Found products: " + ", ".join(product_info)}
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Could not connect to a service. Details: {e.details()}"}

async def search_products(query: str) -> dict:
    """Searches for products by name or description."""
    try:
        async with grpc.aio.insecure_channel('localhost:3550') as channel:
            stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
            request = demo_pb2.SearchProductsRequest(query=query)
            response = await stub.SearchProducts(request)
            if not response.results:
                return {"status": "success", "report": f"No products found for '{query}'."}
            product_names = [p.name for p in response.results]
            return {"status": "success", "report": f"Found products for '{query}': " + ", ".join(product_names)}
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Could not connect to a service. Details: {e.details()}"}

async def get_product_price(product_name: str) -> dict:
    """Gets the price of a specific product by its name."""
    try:
        async with grpc.aio.insecure_channel('localhost:3550') as channel:
            stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
            search_request = demo_pb2.SearchProductsRequest(query=product_name)
            search_response = await stub.SearchProducts(search_request)
            if len(search_response.results) == 1:
                product = search_response.results[0]
                price = f"{product.price_usd.units}.{product.price_usd.nanos // 10000000:02d} {product.price_usd.currency_code}"
                return {"status": "success", "report": f"The price of {product.name} is {price}."}
            elif len(search_response.results) > 1:
                product_names = [p.name for p in search_response.results]
                return {"status": "success", "report": f"Found multiple products for '{product_name}': {', '.join(product_names)}. Please be more specific."}
            else:
                return {"status": "success", "report": f"Could not find product '{product_name}'."}
    except grpc.RpcError as e:
        return {"status": "error", "error_message": f"Could not connect to a service. Details: {e.details()}"}

# --- MCP Toolset for External Tools ---
shipping_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'external_shipping_tracker', 'shipping_server.py'))

external_tools = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'external_shipping_tracker', 'venv', 'bin', 'python3')),
            args=[shipping_server_path],
        )
    )
)

# Define the agent
root_agent = Agent(
    name="online_boutique_agent",
    model="gemini-2.0-flash",
    description="An agent that can interact with the Online Boutique application and external services.",
    instruction="You are a helpful agent that can answer user questions about the Online Boutique, manage a shopping cart, and place orders. You must have a user ID set before you can manage the cart or place an order. When the user wants to check out, ask for their information one piece at a time, starting with their email. Once you have all the information, call the place_order tool.",
    tools=[
        list_products, search_products, get_product_price, 
        add_item_to_cart, get_cart, empty_cart, place_order, set_user_id,
        track_order,
        external_tools
    ],
)
