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
    public Result downloadDataset(@RequestParam(required = false,value = "taskid") Integer taskId, HttpServletResponse response) {
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

    @PostMapping("/downloadMultiple")
    public Result downloadMultipleDatasets(@RequestBody Map<String,Object> map, HttpServletResponse response) {
        List<Integer> taskIds = (List<Integer>) map.get("taskIds");
        
        if (taskIds == null || taskIds.isEmpty()) {
            return ResultGenerator.getFailResult("请提供有效的任务ID数组");
        }
        
        // 创建临时目录来合并数据集
        Path tempDir = Paths.get(System.getProperty("user.dir"), "merged_coco");
        Path tempImagesDir = Paths.get(tempDir.toString(), "images");
        Path tempAnnotationsDir = Paths.get(tempDir.toString(), "annotations");
        
        // 确保目录存在，如果已存在则先删除
        try {
            if (Files.exists(tempDir)) {
                deleteDirectoryRecursively(tempDir);
            }
            Files.createDirectories(tempDir);
            Files.createDirectories(tempImagesDir);
            Files.createDirectories(tempAnnotationsDir);
        } catch (IOException e) {
            e.printStackTrace();
            return ResultGenerator.getFailResult("创建临时目录失败: " + e.getMessage());
        }
        
        // 收集所有数据集的信息
        List<Map<String, Object>> mergedImages = new ArrayList<>();
        List<Map<String, Object>> mergedAnnotations = new ArrayList<>();
        List<Map<String, Object>> mergedCategories = new ArrayList<>();
        final int[] counters = {0, 0, 1}; // imageIdOffset, annotationIdOffset, currentImageId
        
        // 用于跟踪文件名，避免重复
        Map<String, Integer> fileNameMap = new HashMap<>();
        
        // 处理每个任务
        for (Integer taskId : taskIds) {
            Path sourcePath = Paths.get(System.getProperty("user.dir") + File.separator + "src/main/java/com/example/labelMark/resource/public/dataset/COCO_" + taskId);
            
            if (!Files.exists(sourcePath)) {
                System.out.println("任务ID " + taskId + " 的数据集不存在，已跳过");
                continue;
            }
            
            // 读取annotations.json
            try {
                Path annotationsPath = Paths.get(sourcePath.toString(), "annotations", "annotations.json");
                if (!Files.exists(annotationsPath)) {
                    System.out.println("任务ID " + taskId + " 的annotations.json不存在，已跳过");
                    continue;
                }
                
                // 使用ObjectMapper解析JSON
                ObjectMapper mapper = new ObjectMapper();
                JsonNode data = mapper.readTree(new File(annotationsPath.toString()));
                
                // 处理图像
                if (data.has("images")) {
                    JsonNode imagesNode = data.get("images");
                    if (!imagesNode.isArray()) {
                        // 单个图像对象情况
                        String fileName = imagesNode.get("file_name").asText();
                        
                        // 检查文件名是否已存在，如果存在则添加任务ID前缀
                        String actualFileName = fileName;
                        if (fileNameMap.containsKey(fileName)) {
                            // 文件名冲突，添加任务ID前缀
                            actualFileName = "task_" + taskId + "_" + fileName;
                        }
                        fileNameMap.put(actualFileName, counters[2]); // 记录文件名与ID的映射
                        
                        // 复制图像文件，保留原始文件名
                        Path sourceImagePath = Paths.get(sourcePath.toString(), "images", fileName);
                        Path targetImagePath = Paths.get(tempImagesDir.toString(), actualFileName);
                        Files.copy(sourceImagePath, targetImagePath, StandardCopyOption.REPLACE_EXISTING);
                        
                        // 创建新图像对象并添加到合并集合
                        Map<String, Object> newImage = new HashMap<>();
                        newImage.put("file_name", actualFileName);
                        newImage.put("id", counters[2]); // currentImageId
                        newImage.put("width", imagesNode.get("width").asInt());
                        newImage.put("height", imagesNode.get("height").asInt());
                        mergedImages.add(newImage);
                        counters[2]++; // currentImageId++
                    } else {
                        // 处理图像数组
                        for (JsonNode image : imagesNode) {
                            String fileName = image.get("file_name").asText();
                            
                            // 检查文件名是否已存在，如果存在则添加任务ID前缀
                            String actualFileName = fileName;
                            if (fileNameMap.containsKey(fileName)) {
                                // 文件名冲突，添加任务ID前缀
                                actualFileName = "task_" + taskId + "_" + fileName;
                            }
                            fileNameMap.put(actualFileName, counters[2]); // 记录文件名与ID的映射
                            
                            // 复制图像文件，保留原始文件名
                            Path sourceImagePath = Paths.get(sourcePath.toString(), "images", fileName);
                            Path targetImagePath = Paths.get(tempImagesDir.toString(), actualFileName);
                            Files.copy(sourceImagePath, targetImagePath, StandardCopyOption.REPLACE_EXISTING);
                            
                            // 创建新图像对象并添加到合并集合
                            Map<String, Object> newImage = new HashMap<>();
                            newImage.put("file_name", actualFileName);
                            newImage.put("id", counters[2]); // currentImageId
                            newImage.put("width", image.get("width").asInt());
                            newImage.put("height", image.get("height").asInt());
                            mergedImages.add(newImage);
                            counters[2]++; // currentImageId++
                        }
                    }
                }
                
                // 处理注释
                if (data.has("annotations")) {
                    JsonNode annotationsNode = data.get("annotations");
                    if (annotationsNode.isArray()) {
                        for (JsonNode annotation : annotationsNode) {
                            // 获取原始图像ID
                            int originalImgId = annotation.get("img_id").asInt();
                            final int imageIdOffset = counters[0];
                            final int annotationIdOffset = counters[1];
                            
                            // 创建新注释对象
                            Map<String, Object> newAnnotation = new HashMap<>();
                            // 复制所有字段
                            annotation.fields().forEachRemaining(entry -> {
                                String key = entry.getKey();
                                JsonNode value = entry.getValue();
                                if ("id".equals(key)) {
                                    newAnnotation.put(key, annotationIdOffset + value.asInt());
                                } else if ("img_id".equals(key)) {
                                    newAnnotation.put(key, imageIdOffset + value.asInt());
                                } else {
                                    if (value.isArray()) {
                                        // 处理数组类型
                                        List<Object> list = new ArrayList<>();
                                        for (JsonNode item : value) {
                                            if (item.isArray()) {
                                                // 处理嵌套数组（如segmentation）
                                                List<Object> innerList = new ArrayList<>();
                                                for (JsonNode innerItem : item) {
                                                    if (innerItem.isNumber()) {
                                                        innerList.add(innerItem.asDouble());
                                                    } else {
                                                        innerList.add(innerItem.asText());
                                                    }
                                                }
                                                list.add(innerList);
                                            } else if (item.isNumber()) {
                                                list.add(item.asDouble());
                                            } else {
                                                list.add(item.asText());
                                            }
                                        }
                                        newAnnotation.put(key, list);
                                    } else if (value.isObject()) {
                                        // 处理对象类型
                                        Map<String, Object> obj = new HashMap<>();
                                        value.fields().forEachRemaining(e -> {
                                            if (e.getValue().isNumber()) {
                                                obj.put(e.getKey(), e.getValue().asDouble());
                                            } else {
                                                obj.put(e.getKey(), e.getValue().asText());
                                            }
                                        });
                                        newAnnotation.put(key, obj);
                                    } else if (value.isNumber()) {
                                        newAnnotation.put(key, value.asDouble());
                                    } else {
                                        newAnnotation.put(key, value.asText());
                                    }
                                }
                            });
                            
                            mergedAnnotations.add(newAnnotation);
                        }
                    }
                }
                
                // 合并类别
                if (data.has("categories")) {
                    JsonNode categoriesNode = data.get("categories");
                    if (categoriesNode.isArray()) {
                        for (JsonNode category : categoriesNode) {
                            int categoryId = category.get("id").asInt();
                            boolean exists = mergedCategories.stream()
                                .anyMatch(c -> ((Number)c.get("id")).intValue() == categoryId);
                            
                            if (!exists) {
                                Map<String, Object> newCategory = new HashMap<>();
                                category.fields().forEachRemaining(entry -> {
                                    if (entry.getValue().isNumber()) {
                                        newCategory.put(entry.getKey(), entry.getValue().asDouble());
                                    } else {
                                        newCategory.put(entry.getKey(), entry.getValue().asText());
                                    }
                                });
                                mergedCategories.add(newCategory);
                            }
                        }
                    } else {
                        // 单个类别对象
                        int categoryId = categoriesNode.get("id").asInt();
                        boolean exists = mergedCategories.stream()
                            .anyMatch(c -> ((Number)c.get("id")).intValue() == categoryId);
                        
                        if (!exists) {
                            Map<String, Object> newCategory = new HashMap<>();
                            categoriesNode.fields().forEachRemaining(entry -> {
                                if (entry.getValue().isNumber()) {
                                    newCategory.put(entry.getKey(), entry.getValue().asDouble());
                                } else {
                                    newCategory.put(entry.getKey(), entry.getValue().asText());
                                }
                            });
                            mergedCategories.add(newCategory);
                        }
                    }
                }
                
                // 更新偏移量
                counters[0] = counters[2] - 1; // imageIdOffset = currentImageId - 1
                if (data.has("annotations")) {
                    JsonNode annotationsNode = data.get("annotations");
                    counters[1] += annotationsNode.isArray() ? annotationsNode.size() : 1; // annotationIdOffset += size
                }
                
                // 复制images目录下的所有文件（不仅仅是在annotations.json中引用的文件）
                Path sourceImagesDir = Paths.get(sourcePath.toString(), "images");
                if (Files.exists(sourceImagesDir)) {
                    try {
                        Files.list(sourceImagesDir).forEach(imagePath -> {
                            if (!Files.isDirectory(imagePath)) {
                                String fileName = imagePath.getFileName().toString();
                                // 检查文件名是否已存在，如果存在则添加任务ID前缀
                                String actualFileName = fileName;
                                if (fileNameMap.containsKey(fileName) && !fileNameMap.containsKey(actualFileName)) {
                                    // 文件名冲突，添加任务ID前缀
                                    actualFileName = "task_" + taskId + "_" + fileName;
                                }
                                
                                // 如果文件尚未被复制（不在fileNameMap中），则复制它
                                if (!fileNameMap.containsKey(actualFileName)) {
                                    Path targetImagePath = Paths.get(tempImagesDir.toString(), actualFileName);
                                    try {
                                        Files.copy(imagePath, targetImagePath, StandardCopyOption.REPLACE_EXISTING);
                                        // 注意：这里不更新counters[2]，因为这些额外的图像不会被添加到annotations.json中
                                    } catch (IOException e) {
                                        e.printStackTrace();
                                    }
                                }
                            }
                        });
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                }
                
            } catch (Exception e) {
                e.printStackTrace();
                System.out.println("处理任务ID " + taskId + " 时出错: " + e.getMessage());
            }
        }
        
        // 写入合并后的annotations.json
        Map<String, Object> mergedData = new HashMap<>();
        mergedData.put("images", mergedImages);
        mergedData.put("annotations", mergedAnnotations);
        mergedData.put("categories", mergedCategories);
        
        try {
            ObjectMapper mapper = new ObjectMapper();
            mapper.enable(SerializationFeature.INDENT_OUTPUT);
            mapper.writeValue(new File(tempAnnotationsDir.toString() + "/annotations.json"), mergedData);
            
            // 创建压缩文件
            Path zipPath = Paths.get(System.getProperty("user.dir"), "merged_coco.zip");
            if (Files.exists(zipPath)) {
                Files.delete(zipPath);
            }
            Files.createFile(zipPath);
            
            // 创建ZIP文件
            try (ZipOutputStream zos = new ZipOutputStream(new FileOutputStream(zipPath.toFile()))) {
                Files.walk(tempDir).filter(path -> !Files.isDirectory(path)).forEach(path -> {
                    ZipEntry zipEntry = new ZipEntry("merged_coco/" + tempDir.relativize(path).toString());
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
            
            // 删除临时文件和目录
            Files.delete(zipPath);
            deleteDirectoryRecursively(tempDir);
            
            // 设置响应头
            response.addHeader("Content-Disposition", "attachment; filename=merged_coco.zip");
            response.addHeader("Content-Type", "application/zip");
            
            // 返回压缩文件的字节数组
            return ResultGenerator.getSuccessResult(zipContent);
            
        } catch (IOException e) {
            e.printStackTrace();
            try {
                deleteDirectoryRecursively(tempDir);
            } catch (IOException ex) {
                ex.printStackTrace();
            }
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
        Path StuffImgPath = Paths.get(String.valueOf(outputDirImage), "train_"+taskId+".jpeg");
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
