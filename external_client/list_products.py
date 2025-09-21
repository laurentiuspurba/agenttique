
import grpc
import demo_pb2
import demo_pb2_grpc

def main():
    # Connect to the server
    channel = grpc.insecure_channel('localhost:3550')
    stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)

    # Call the ListProducts method
    response = stub.ListProducts(demo_pb2.Empty())

    # Print the products
    print("Products:")
    for product in response.products:
        print(f"- {product.name}")

if __name__ == '__main__':
    main()
