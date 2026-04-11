#include "esp_camera.h"
#include <WiFi.h>

// WiFi credentials
const char* ssid = "test";
const char* password = "12345678";

// Flask server
const char* serverName = "your flask server ip"; // Flask IP
const int serverPort = 5001;

// Camera pins
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

void setup() {
  Serial.begin(115200);

  // Camera setup
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM; config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000; 
  config.pixel_format = PIXFORMAT_JPEG; 
  config.frame_size = FRAMESIZE_VGA; 
  config.jpeg_quality = 15; 
  config.fb_count = 1;

  if(esp_camera_init(&config) != ESP_OK){
    Serial.println("Camera init failed");
    return;
  }

  // Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
  Serial.println(WiFi.localIP());
}

void loop() {
  camera_fb_t *fb = esp_camera_fb_get();
  if(!fb){
    Serial.println("Camera capture failed");
    delay(5000);
    return;
  }

  WiFiClient client;
  if(!client.connect(serverName, serverPort)){
    Serial.println("Connection to server failed");
    esp_camera_fb_return(fb);
    delay(5000);
    return;
  }

  // Prepare multipart form-data
  String boundary = "ESP32CAM";
  String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"img.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";

  // Send HTTP request manually
  client.print(String("POST /upload HTTP/1.1\r\n") +
               "Host: " + serverName + "\r\n" +
               "Content-Type: multipart/form-data; boundary=" + boundary + "\r\n" +
               "Content-Length: " + String(head.length() + fb->len + tail.length()) + "\r\n" +
               "Connection: close\r\n\r\n");

  client.print(head);

  // Send image in chunks
  size_t sent = 0;
  while(sent < fb->len){
    size_t chunkSize = fb->len - sent;
    client.write(fb->buf + sent, chunkSize);
    sent += chunkSize;
  }

  client.print(tail);

  // Wait response
  while(client.connected()){
    if(client.available()){
      String line = client.readStringUntil('\n');
      Serial.println(line);
    }
  }

  client.stop();
  esp_camera_fb_return(fb);

  delay(15000); // 15 seconds between uploads
}