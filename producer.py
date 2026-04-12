import pika
import json
import os

def send_rabbitmq_notification(name, workout, time):
    # Fetch the RabbitMQ URL from environment variables
    amqp_url = "amqps://cxrcnoch:kBxX-_Zb-qkdJaeJ1F-8S1Em14sQa0Uw@gerbil.rmq.cloudamqp.com/cxrcnoch"
    
    try:
        params = pika.URLParameters(amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        # Ensure the queue exists
        channel.queue_declare(queue='gym_bookings', durable=True)
        
        # The message payload
        message = {
            "event": "NEW_BOOKING",
            "user": name,
            "zone": workout,
            "time": time
        }
        
        # Send to the queue
        channel.basic_publish(
            exchange='',
            routing_key='gym_bookings',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2) # Persistent message
        )
        connection.close()
        print(f"[RabbitMQ] Successfully queued booking for {name}")
    except Exception as e:
        print(f"[RabbitMQ Error] {e}")