import pika
import json
import os

def callback(ch, method, properties, body):
    # Decode the JSON message sent by producer.py
    message = json.loads(body)
    
    # Process the notification
    print(f" [x] NEW ALERT: {message['user']} just booked the {message['zone']} at {message['time']}!")
    
    # Tell RabbitMQ the message was successfully processed
    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_consuming():
    amqp_url = "amqps://cxrcnoch:kBxX-_Zb-qkdJaeJ1F-8S1Em14sQa0Uw@gerbil.rmq.cloudamqp.com/cxrcnoch"
    
    try:
        params = pika.URLParameters(amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        channel.queue_declare(queue='gym_bookings', durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='gym_bookings', on_message_callback=callback)
        
        print(' [*] Consumer active. Waiting for gym bookings. To exit press CTRL+C')
        channel.start_consuming()
    except Exception as e:
        print(f"[RabbitMQ Error] {e}")

if __name__ == '__main__':
    start_consuming()