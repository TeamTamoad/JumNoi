# JumNoi
Cloud-native LINE chatbot service that detect and note expiration date of items for user

## Demo
https://user-images.githubusercontent.com/43115371/174498289-9ea7f7d0-e63d-4324-8ba0-c71bb3a9d715.mp4

## Architecture
![image2](https://user-images.githubusercontent.com/43115371/174498464-eac59f9b-1076-45e6-8cde-4834d01a79b9.png)

### Components
#### LINE
ส่ง webhook event ไปที่ URL ของ API Gateway ทุกครั้งที่มีข้อความจากผู้ใช้
#### API Gateway
เป็นตัวกลางการเชื่อมต่อระหว่าง LINE – jumnoiProxy Lambda และระหว่าง Dialogflow – jumnoiFulfillment Lambda
#### jumnoiProxy
แม้ว่า Dialogflow จะสามารถเชื่อมกับ LINE ได้โดยตรง แต่เนื่องจาก Dialogflow รองรับเฉพาะข้อความประเภท text message จึงต้องมี jumnoiProxy เพื่อรับ event จาก LINE ผ่าน API Gateway แล้วจัดการข้อมูล โดยกรณีที่เป็นข้อความประเภท text หรือ image จะทำการแปลงให้อยู่ในรูป text message แล้วส่งให้ Dialogflow แต่ถ้าเป็นข้อความประเภทอื่นจะส่งข้อความตอบกลับไปยัง LINE โดยตรงว่าไม่เข้าใจข้อความประเภทนั้น ๆ
#### jumnoiFulfillment
ในการตอบกลับข้อความของ Dialogflow สามารถเลือกได้ว่าจะเป็นการตอบกลับไปยัง LINE โดยตรงหรือเรียกใช้ service อื่นเพื่อจัดการ event โดยในที่นี้จะใช้ jumnoiFulfillment Lambda ในการจัดการ event โดยตัว jumnoiFulfillment จะมีการเรียกใช้ Rekognition, DynamoDB และ S3 เพื่อทำการอ่านวันหมดอายุจากรูปภาพแล้วเก็บลง Database หรืออ่านข้อมูลจาก Database ตาม Dialogflow intent ที่กำลัง active ในขณะนั้น
#### jumnoiDaily
เช็คข้อมูลสินค้าที่มีวันหมดอายุในวันรุ่งขึ้นจาก DynamoDB ดึงรูปภาพจาก S3 เพื่อส่งไปยัง LINE
#### jumnoiDelete
เช็คข้อมูลวันหมดอายุที่ผ่านไปแล้วจาก DynamoDB แล้วลบ item จาก DynamoDB และ S3 objects ที่เกี่ยวข้องกับ item นั้น ๆ
#### Dialogflow
รับ event ที่จาก jumnoiProxy Lambda แล้วเช็คตาม intent ของ Dialogflow เพื่อ handle event ตาม intent นั้น ๆ โดยแบ่งเป็น 2 กรณี ได้แก่ กรณีส่งข้อความตอบกลับไปยัง LINE โดยตรง และกรณีเรียก jumnoiFulfillment เพื่อ handle business logic
Eventbridge
#### jumnoiDaily
เรียก jumnoiDaily Lambda ทุกวัน เวลา 18:00 น.
#### jumnoiDelete
เรียก jumnoiDelete Lambda ทุก 7 วัน
#### Rekognition
ถูกเรียกใช้โดย Lambda (jumnoiFulfillment, jumnoiDaily, jumnoiDelete)
#### DynamoDB
ถูกเรียกใช้โดย Lambda (jumnoiDaily, jumnoiDelete)
#### S3
ถูกเรียกใช้โดย Lambda (jumnoiDaily, jumnoiDelete)
