import xml.etree.ElementTree as ET
import json
import os

def convert_xml_to_json(xml_filename, json_filename):
    if not os.path.exists(xml_filename):
        print(f"Error: {xml_filename} not found!")
        return

    print(f"Reading {xml_filename}...")
    tree = ET.parse(xml_filename)
    root = tree.getroot()

    bookings_list = []

    # Loop through each <booking> tag in the XML
    for booking in root.findall('booking'):
        booking_data = {
            "user_id": int(booking.find('user_id').text),
            "name": booking.find('name').text,
            "workout": booking.find('workout').text,
            "time": booking.find('time').text
        }
        bookings_list.append(booking_data)

    # Write the list of dictionaries to a JSON file
    with open(json_filename, 'w') as json_file:
        json.dump(bookings_list, json_file, indent=4)

    print(f"Successfully converted {len(bookings_list)} records to {json_filename}!")

if __name__ == "__main__":
    convert_xml_to_json('bookings.xml', 'bookings.json')