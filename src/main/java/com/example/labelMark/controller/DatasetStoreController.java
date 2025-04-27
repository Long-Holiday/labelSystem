package com.example.labelMark.controller;

import com.example.labelMark.domain.DatasetStore;
import com.example.labelMark.domain.ImageInfo;
import com.example.labelMark.domain.Mark;
import com.example.labelMark.domain.Task;

import com.example.labelMark.service.*;
import com.example.labelMark.utils.*;
import com.example.labelMark.vo.constant.Result;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import org.json.JSONObject;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletResponse;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-05-08
 */
@RestController
@RequestMapping("/datasetStore")
public class DatasetStoreController {

    @Resource
    private DatasetStoreService datasetStoreService;

    @Resource
    private TaskService taskService;

    @Resource
    private MarkService markService;

    @Resource
    private TypeService typeService;

    @Resource
    private GeoServerRESTClient geoServerRESTClient;
    @Resource
    private GeoServerService geoServerService;

    @GetMapping("/getTotalImgNumBySampleId")
    public Result getTotalImgNumBySampleId(int sampleId) {
        int sum = datasetStoreService.getTotalImgNumBySampleId(sampleId);
        return ResultGenerator.getSuccessResult(sum);
    }


    @GetMapping("/findImgSrcTypeNameBySampleId")
    public Result findImgSrcTypeNameBySampleId(int sampleId, int pageSize, int current) {
        List<ImageInfo> imageInfo = datasetStoreService.findImgSrcTypeNameBySampleId(sampleId, pageSize, current);
        return ResultGenerator.getSuccessResult(imageInfo);
    }


    @GetMapping("/getDataSet")
    public Result getDataSet(@RequestParam String username
            ,@RequestParam Integer isAdmin
            ,@RequestParam(required = false) Integer isPublic) {

        List<Map<String, Object>> taskIdArr;

        if (isAdmin == 1) {
            System.out.println("Admin查询");
            taskIdArr = taskService.findAllTask();
        } else {
            System.out.println("User查询");
            if (isPublic == 1) {
                taskIdArr = taskService.findPublicTask();
            } else {
                taskIdArr = taskService.findTasksByUsername(username);
            }
        }
        System.out.println(taskIdArr);

        Map<String, Object> res = new HashMap<>();;
        if (!taskIdArr.isEmpty()) {

            List<Map<String, Object>> taskDatasetInfos = new ArrayList<>();
            List<String> usernameLists = new ArrayList<>();


            for (Map<String, Object> map : taskIdArr) {

                Object value = map.get("task_id");
                System.out.println(value);
                List<Map<String, Object>> datasetInfoList = datasetStoreService.findDatasetByTaskId((Integer) value);
                taskDatasetInfos.addAll(datasetInfoList);

                List<String> userList = taskService.findUserListByTaskId((Integer) value);
                usernameLists.addAll(userList);

            }

            if (!taskDatasetInfos.isEmpty()) {
                res.put("taskDatasetInfos", taskDatasetInfos);
                res.put("usernameLists", usernameLists);
            }

        }
        return ResultGenerator.getSuccessResult(res);
    }


    @GetMapping("/getSampleImageList")
    public Result getSampleImageList(@RequestParam int pageSize
            ,@RequestParam int current
            ,@RequestParam(required = false) Integer sampleId){
        int total = datasetStoreService.getTotalImgNumBySampleId(sampleId);
        List<ImageInfo> imageInfos = datasetStoreService.findImgSrcTypeNameBySampleId(sampleId, pageSize, current);
        Map<String, Object> res = new HashMap<>();
        res.put("total", total);
        res.put("imageInfos", imageInfos);

        return ResultGenerator.getSuccessResult(res);
    }

    @PostMapping("/setDatasetStatus")
    public Result setDatasetStatus(@RequestBody Map<String,Object> map){
        Integer isPublic = Integer.valueOf(map.get("isPublic").toString());
        Integer sampleId = Integer.valueOf(map.get("sampleId").toString());
        datasetStoreService.updateDatasetStatusBySampleId(isPublic, sampleId);
        return ResultGenerator.getSuccessResult();
    }

    @GetMapping("/deleteDataset")
    public Result deleteDataset(int sampleId, int taskId){
        datasetStoreService.deleteDatastoreById(sampleId);
        String markTaskId = "mark_" + taskId;
        Path DOWNLOAD_DIR = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/public/dataset_temp/",markTaskId);
        Path OUTPUT_DIR = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/public/dataset/COCO_" + taskId);

        try {
            // 删除 DOWNLOAD_DIR
            deleteDirectoryRecursively(DOWNLOAD_DIR);
            // 删除 OUTPUT_DIR
            deleteDirectoryRecursively(OUTPUT_DIR);
        } catch (IOException e) {
            e.printStackTrace();
            return ResultGenerator.getFailResult("Failed to delete directories");
        }

        return ResultGenerator.getSuccessResult("Directories deleted successfully");
    }

    private void deleteDirectoryRecursively(Path directory) throws IOException {
        if (Files.exists(directory)) {
            Files.walkFileTree(directory, new SimpleFileVisitor<Path>() {
                @Override
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    Files.delete(file);
                    return FileVisitResult.CONTINUE;
                }

                @Override
                public FileVisitResult postVisitDirectory(Path dir, IOException exc) throws IOException {
                    Files.delete(dir);
                    return FileVisitResult.CONTINUE;
                }
            });
        }
    }


    @GetMapping("/download")
    public Result downloadDataset(@RequestParam(required = false,value = "taskid") Integer taskId, HttpServletResponse response){

        Path outputDir = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/public/dataset/COCO_" + taskId);

        // 检查文件读取目录是否存在
        if (!Files.exists(outputDir)) {
            return ResultGenerator.getFailResult("指定的目录不存在: " + outputDir);
        }

        try {
            // 创建压缩文件的路径
            Path zipPath = Paths.get(System.getProperty("user.dir"), "COCO.zip");
            Files.createFile(zipPath);
//            createDirectory(zipPath, "创建COCO.zip文件路径");
            // 计算输出路径
//            Path outputPath = Paths.get(outputDir, "COCO_" + taskId);

            // 创建压缩包  Files.newOutputStream(zipPath)
            try (ZipOutputStream zos = new ZipOutputStream(new FileOutputStream(String.valueOf(zipPath)))) {
                // 读取输出路径下的所有文件和子文件夹
                Files.walk(outputDir).filter(path -> !Files.isDirectory(path)).forEach(path -> {
                    ZipEntry zipEntry = new ZipEntry(outputDir.relativize(path).toString());
                    try {
                        zos.putNextEntry(zipEntry);
                        Files.copy(path, zos);
                        zos.closeEntry();
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                });
            }

            // 读取压缩文件到字节数组
            byte[] zipContent = Files.readAllBytes(zipPath);

            // 删除压缩文件
            Files.delete(zipPath);

            // 设置响应头
            /*HttpHeaders headers = new HttpHeaders();
            headers.add("Content-Disposition", "attachment; filename=files.zip");
            headers.add("Content-Type", "application/zip");*/
            response.addHeader("Content-Disposition", "attachment; filename=files.zip");
            response.addHeader("Content-Type", "application/zip");
            // 返回压缩文件的字节数组
            return ResultGenerator.getSuccessResult(zipContent);

        } catch (IOException e) {
            e.printStackTrace();
            return ResultGenerator.getFailResult(e.getMessage());
        }

    }

    @PostMapping("/generateDataset")
    public Result generateDataset(@RequestBody Map<String,Object> map) throws IOException {
        Integer taskId = Integer.valueOf(map.get("taskid").toString());
        Integer idExist = datasetStoreService.hasGenerateDataset(taskId);
        System.out.println(idExist);
        if (idExist != 0){
            System.out.println("该样本已存在");
            return ResultGenerator.getSuccessResult("该样本已存在");
        }

        Task task = taskService.selectTaskById(taskId);

        List<Mark> marks =markService.selectMarkById(taskId);

        int sampleId = datasetStoreService.createDataset(taskId);
        System.out.println(sampleId);
        String markTaskId = "mark_" + taskId;
        Path downloadDir = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/public/dataset_temp/", markTaskId);
        Path outputDir = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/public/dataset/COCO_" + taskId);
        Path outputDirImage = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/public/dataset/COCO_" + taskId + "/images");
        Path outputDirAnnotations = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/public/dataset/COCO_" + taskId + "/annotations");

        createDirectoryIfNotExists(downloadDir);
        createDirectory(outputDir, "创建coco文件夹");
        createDirectory(outputDirImage, "创建coco/images文件夹");
        createDirectory(outputDirAnnotations, "创建coco/annotations文件夹");

//        String jsonStr = geoServerRESTClient.GeoServerString(taskService.getServerById(taskId));
//        System.out.println(jsonStr);
//        // 创建一个JSONObject来解析JSON字符串
//        JSONObject jsonObj = new JSONObject(jsonStr);
//        // 从JSONObject中提取图层信息
//        JSONObject featureType = jsonObj.getJSONObject("featureType");
//        // 提取图层的空间参考系统（SRS）
//        String srs = featureType.getString("srs");
//        // 从图层信息中提取边界框（nativeBoundingBox）
//        JSONObject boundingBox = featureType.getJSONObject("nativeBoundingBox");

        // 获取图层信息
        String layerInfo = geoServerRESTClient.getLayerInfo(taskService.getServerById(taskId));
        if (layerInfo.startsWith("ERROR")) {
            System.out.println(layerInfo);
            return ResultGenerator.getFailResult("ERROR");
        }

        // 使用 Jackson 解析 JSON 响应
        ObjectMapper objectMapper = new ObjectMapper();
        JsonNode rootNode = objectMapper.readTree(layerInfo);
        String coverageHref = rootNode.path("layer").path("resource").path("href").asText();

        // 获取 coverage 详细信息
        String coverageInfo = geoServerRESTClient.getCoverageInfo(coverageHref);
        if (coverageInfo.startsWith("ERROR")) {
            System.out.println(coverageInfo);
            return ResultGenerator.getFailResult("ERROR");
        }

        // 解析 coverage 信息
        JsonNode coverageRootNode = objectMapper.readTree(coverageInfo);
        String srs = coverageRootNode.path("coverage").path("srs").asText();

        //更正geoserver坐标系，latLonBoundingBox为4326，nativeBoundingBox为3857
//        JsonNode bboxNode = coverageRootNode.path("coverage").path("latLonBoundingBox");
        JsonNode bboxNode = coverageRootNode.path("coverage").path("nativeBoundingBox");
//        String bbox = bboxNode.path("minx").asText() + "," + bboxNode.path("miny").asText() + "," + bboxNode.path("maxx").asText() + "," + bboxNode.path("maxy").asText();

        System.out.println("SRS: " + srs);
        System.out.println("Bounding Box: " + bboxNode);

        // 提取minx、maxx、miny和maxy的值
        double minx = bboxNode.path("minx").asDouble();
        double maxx = bboxNode.path("maxx").asDouble();
        double miny = bboxNode.path("miny").asDouble();
        double maxy = bboxNode.path("maxy").asDouble();

        double height = 2048;
        double width = Math.ceil(((maxx - minx) / (maxy - miny)) * height);

        // 修正 minx, miny, maxx, maxy 顺序
//        String bbox1 = String.format("%f,%f,%f,%f", minx, maxx, miny, maxy);
        String bbox1 = String.format("%f,%f,%f,%f", minx, miny, maxx, maxy);

        System.out.println("Parsed BBOX from coverageInfo: minx=" + minx + ", maxx=" + maxx + ", miny=" + miny + ", maxy=" + maxy);
        System.out.println("Formatted BBOX string: " + bbox1);


        Map<String, Object> images = new HashMap<>();
        images.put("file_name", "train_" + taskId + ".jpeg");
        images.put("id", 1);
        images.put("width", width);
        images.put("height", height);

        ResponseEntity<byte[]> result = geoServerService.getGeoserverImg(
                taskService.getServerById(taskId),
                (int) Math.round(width),  // 使用计算出的宽度
                (int) Math.round(height), // 使用计算出的高度
                bbox1,
                srs // 使用从 GeoServer 获取的 srs
        );
//        ResponseEntity<byte[]> result = geoServerService.getGeoserverImg(
//                taskService.getServerById(taskId),
//                256,
//                256,
//                bbox1,
//                "EPSG:3857"
//        );
        System.out.println(result);
        // 区分样本集类型并确定文件路径
        Path filePath = Paths.get(String.valueOf(outputDirImage), "train_"+taskId+".tif");

        // 将响应流中的数据写入文件
        try (FileOutputStream fos = new FileOutputStream(filePath.toFile())) {
            byte[] body = result.getBody();
            if (body != null && body.length > 0) {
                fos.write(body);
                System.out.println("Image saved successfully to " + filePath);
            } else {
                System.err.println("No data received from GeoServer.");
            }
        } catch (IOException e) {
            e.printStackTrace();
            System.err.println("Error writing file: " + e.getMessage());
        }


        Map<String, Double> tifParams = new HashMap<>();;
        tifParams.put("minx", Math.abs(minx));
        tifParams.put("maxy", Math.abs(maxy));
        tifParams.put("serverHeight", Math.abs(maxy) - Math.abs(miny));
        tifParams.put("serverWidth", Math.abs(maxx) - Math.abs(minx));
        Map<String, Double> dimensions = new HashMap<>();;
        dimensions.put("width", width);
        dimensions.put("height", height);

        List<Map<String, Object>> categories = new ArrayList<>();
        List<Map<String, Object>> annotations = new ArrayList<>();

        // 将tasks集合转为Map集合
        List<Map<String, Object>> mark = DomainToMapList.convertDomainListToMapList(marks);
        List<Map<String, Object>> segmentationArr = CovertCoordinateToPixel.covertCoordinateToPixel(mark, tifParams, dimensions);


//        if(Objects.equals(taskService.getTypeById(taskId), "地物分类")){
//            GenerateStuffImg.generateStuffImg((int) Math.round(width), (int) Math.round(height), segmentationArr, filePath.toString());
//
//        }
        Path StuffImgPath = Paths.get(String.valueOf(outputDirImage), "train_"+taskId+".PNG");
        GenerateStuffImg.generateStuffImg((int) Math.round(width), (int) Math.round(height), segmentationArr, StuffImgPath.toString());

        int i;
        for(i=0; i<segmentationArr.size(); i++){
//            String geom = (String) segmentationArr.get(i).get("geom");
//            Integer taskId = (Integer) segmentationArr.get(i).get("task_id");
            Integer userId = (Integer) segmentationArr.get(i).get("user_id");
            Integer typeId = (Integer) segmentationArr.get(i).get("type_id");
            String typeColor = (String) segmentationArr.get(i).get("type_color");
            List<Double> segmentation = (List<Double>) segmentationArr.get(i).get("segmentation");
            double[] bbox2 = (double[]) segmentationArr.get(i).get("bbox");
            String geoBbox = (String) segmentationArr.get(i).get("geoBbox");


            // 检查 `categories` 列表中是否已有 `typeId`
            boolean typeExists = categories.stream().anyMatch(cat -> (int) cat.get("id") == typeId);
            if (!typeExists) {
                String typeName = typeService.getTypeNameById(typeId);
                System.out.println(typeId + " " + typeName);

                Map<String, Object> category = new HashMap<>();
                category.put("name", typeName);
                category.put("id", typeId);
                category.put("color", typeColor);
                categories.add(category);
            }

            Map<String, Object> annotation = new HashMap<>();
            annotation.put("category_id", typeId);
            annotation.put("img_id", 1);
            annotation.put("bbox", bbox2);
            annotation.put("segmentation", segmentation);
            annotations.add(annotation);

            geoServerService.getGeoserverImg(taskService.getServerById(taskId), 256, 256, geoBbox, "EPSG:3857");

            Path localFilePath = Paths.get(String.valueOf(downloadDir), "mark_" + taskId+"_" + i + ".jpeg");
            // 将响应流中的数据写入文件
            try (FileOutputStream fos = new FileOutputStream(String.valueOf(localFilePath))) {
                fos.write(Objects.requireNonNull(result.getBody()));
            }

            datasetStoreService.insertSampleImgInfo(sampleId, typeId, localFilePath.toString());

            System.out.println("图片" + sampleId + "生成成功！");
        }

        Map<String, Object> json = new HashMap<>();
        json.put("images", images);
        json.put("annotations", annotations);
        json.put("categories", categories);
        ObjectMapper mapper = new ObjectMapper();
        mapper.enable(SerializationFeature.INDENT_OUTPUT); // For pretty print
//        String jsonString = mapper.writeValueAsString(json);
        try {

            // 确保目录存在，如果不存在则创建目录
            File outputDirFile  = outputDirAnnotations.toFile();
            if (!outputDirFile.exists()) {
                outputDirFile.mkdirs();
            }

            // 定义输出文件路径
            File outputFile = new File(outputDirFile, "annotations.json");

            // 将 JSON 写入文件
            mapper.writeValue(outputFile, json);
            System.out.println("JSON 文件生成成功！_java");
        } catch (IOException e) {
            e.printStackTrace();
        }
        return ResultGenerator.getSuccessResult("样本生成成功");
    }


    private static void createDirectoryIfNotExists(Path path) {
        if (Files.notExists(path)) {
            try {
                Files.createDirectories(path);
                System.out.println("Created directory: " + path.toString());
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    private static void createDirectory(Path path, String message) {
        try {
            Files.createDirectories(path);
            System.out.println(message);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }


}
