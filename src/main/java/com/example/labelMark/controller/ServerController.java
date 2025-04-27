package com.example.labelMark.controller;

import com.example.labelMark.service.SysFileService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.json.JSONObject;

import com.example.labelMark.domain.Server;
import com.example.labelMark.service.ServerService;
import com.example.labelMark.utils.GeoServerRESTClient;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;


import javax.annotation.Resource;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Base64;
import java.util.List;
import java.util.Map;

/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-04-15
 */
@RestController
@RequestMapping("/server")
public class ServerController {

    private static final String GEOSERVER_REST_URL = "http://localhost:8081/geoserver/rest";
    private static final String DOWNLOAD_DIR = "src/main/java/com/example/labelMark/resource/img"; // 指定下载目录

    private static final String USERNAME = "admin";
    private static final String PASSWORD = "geoserver";
    @Resource
    private ServerService serverService;
    @Resource
    private SysFileService sysFileService;

    @Resource
    private GeoServerRESTClient geoServerRESTClient;

    @GetMapping("/getServers")
    public Result getServers() {
        List<Server> servers = serverService.getServers();
        return ResultGenerator.getSuccessResult(servers);
    }

    @DeleteMapping("/deleteServer/{serName}")
    public Result deleteServerByName(@PathVariable String serName) {
        try {
            int isDelete = serverService.deleteServerByName(serName);
            if (isDelete < 0) {
                return ResultGenerator.getFailResult("删除失败");
            }
            return ResultGenerator.getSuccessResult("删除成功");
        } catch (Exception e) {
            return ResultGenerator.getFailResult("删除失败" + e.getMessage());
        }
    }


    @PostMapping("/createServer")
    public Result createServer(@RequestBody Map<String, Object> map) {
        try {
            String filename = map.get("filename").toString();
            String publisher = map.get("publisher").toString();
            String publishtime = map.get("publishtime").toString();
            String serdesc = map.get("serdesc").toString();
            String sername = map.get("sername").toString();
            String seryear = map.get("seryear").toString();
            String publishUrl = map.get("publishUrl").toString();
            //创建服务
            Server server = new Server();
            server.setPublishUrl(publishUrl);
            server.setPublisher(publisher);
            server.setPublishTime(publishtime);
            server.setSerDesc(serdesc);
            server.setSerYear(seryear);
            server.setSerName(sername);
            boolean isInserted = serverService.createServer(server);
            if (isInserted) {
//                TODO 使用fileId来唯一限定
                //            更新服务状态为已发布
                sysFileService.updateFileStatus(filename);
                return ResultGenerator.getSuccessResult("创建服务成功");
            } else {
                return ResultGenerator.getFailResult("创建服务失败");
            }
        }catch (Exception e){
            return ResultGenerator.getFailResult("创建失败"+ e.getMessage());
        }
    }

//    @GetMapping ("/downloadServerImg")
//    public Result downloadServerImg(String serverName){
//
//        String jsonStr = geoServerRESTClient.GeoServerString(serverName);
//        System.out.println(jsonStr);
//        // 创建一个JSONObject来解析JSON字符串
//        JSONObject jsonObj = new JSONObject(jsonStr);
//
//        // 从JSONObject中提取图层信息
//        JSONObject featureType = jsonObj.getJSONObject("featureType");
//
//        // 提取图层的名称
////        String name = featureType.getString("name");
//
//        // 提取图层的空间参考系统（SRS）
//        String srs = featureType.getString("srs");
//
//        // 从图层信息中提取边界框（nativeBoundingBox）
//        JSONObject boundingBox = featureType.getJSONObject("nativeBoundingBox");
//
//        // 提取minx、maxx、miny和maxy的值
//        double minx = boundingBox.getDouble("minx");
//        double maxx = boundingBox.getDouble("maxx");
//        double miny = boundingBox.getDouble("miny");
//        double maxy = boundingBox.getDouble("maxy");
//
//        double width = Math.ceil(((maxx - minx) / (maxy - miny)) * 600);
//
//
//        // 构建WMS请求参数
//        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
//        // 在这里WMS服务通常用于请求地图图像，而不是用于下载矢量数据文件（如.shp）。
//        // 如果想从GeoServer下载.shp文件，应该使用WFS（Web Feature Service）而不是WMS。
//        params.add("service", "WMS");
//        params.add("version", "1.1.0");
//        params.add("request", "GetMap");
//        params.add("layers", "LUU:"+ serverName);
//        params.add("styles", "");
//        params.add("bbox", String.format("%f,%f,%f,%f", minx, miny, maxx, maxy));
//        params.add("width", String.valueOf((int)width));
//        params.add("height", "600");
//        params.add("srs", srs);
//        params.add("format", "image/tiff");
//
//        try {
//            // 发送WMS请求
//            HttpClient httpClient = HttpClient.newHttpClient();
//            HttpRequest request = buildRequest("/LUU/wms", params); // 假设 params 是你的查询参数
//
//            HttpResponse<InputStream> response = httpClient.send(request, HttpResponse.BodyHandlers.ofInputStream());
//            System.out.println(response);
//            // 将图片数据写入文件
//            if (response.statusCode() == 500) {
//                // 获取响应体
//                InputStream inputStream = response.body();
//                Path filePath = Paths.get(DOWNLOAD_DIR, serverName + ".jpeg");
//
//                // 将输入流写入文件
//                Files.copy(inputStream, filePath);
//                // 关闭输入流
//                inputStream.close();
//
//                return ResultGenerator.getSuccessResult("Image downloaded successfully to" + filePath);
//            } else {
//                return ResultGenerator.getFailResult("Failed to download image.");
//            }
//        } catch (Exception e) {
//            return ResultGenerator.getFailResult("An error occurred: " + e.getMessage());
//        }
//    }

    @GetMapping ("/downloadServerImg")
    public Result downloadServerImg(String serverName) throws IOException {

            // 获取图层信息
            String layerInfo = geoServerRESTClient.getLayerInfo(serverName);

            // 使用 Jackson 解析 JSON 响应
            ObjectMapper objectMapper = new ObjectMapper();
            JsonNode rootNode = objectMapper.readTree(layerInfo);
            String coverageHref = rootNode.path("layer").path("resource").path("href").asText();

            String auth = USERNAME + ":" + PASSWORD;
            String encodedAuth = Base64.getEncoder().encodeToString(auth.getBytes());

            URL url = new URL(coverageHref);
            HttpURLConnection con = (HttpURLConnection) url.openConnection();
            con.setRequestMethod("GET");
            con.setRequestProperty("Authorization", "Basic " + encodedAuth);

            int responseCode = con.getResponseCode();
            if (responseCode == HttpURLConnection.HTTP_OK) {
                BufferedInputStream in = new BufferedInputStream(con.getInputStream());
                OutputStream out = new FileOutputStream(String.valueOf(Paths.get(DOWNLOAD_DIR, serverName + ".tiff")));

                byte[] buffer = new byte[1024];
                int bytesRead;
                while ((bytesRead = in.read(buffer, 0, 1024)) != -1) {
                    out.write(buffer, 0, bytesRead);
                }

                in.close();
                out.close();

                return ResultGenerator.getSuccessResult("TIFF file successfully downloaded");
            } else {
                return ResultGenerator.getFailResult("GET request not worked. Response code: " + responseCode);
            }


    }

    private String getBasicAuthToken() {
        String auth = USERNAME + ":" + PASSWORD;
        String encodedAuth = Base64.getEncoder().encodeToString(auth.getBytes(StandardCharsets.UTF_8));
        return "Basic " + encodedAuth;
    }

    private HttpRequest buildRequest(String path, MultiValueMap<String, String> queryParams) {
        String encodedPath = URLEncoder.encode(path, StandardCharsets.UTF_8);
        return HttpRequest.newBuilder()
                .uri(URI.create(GEOSERVER_REST_URL + "/" + encodedPath))
                .headers("Authorization", "Basic " + getBasicAuthToken())
                .GET()
                .build();
    }

}
