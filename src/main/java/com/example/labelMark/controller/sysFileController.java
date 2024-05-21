package com.example.labelMark.controller;

import cn.hutool.core.util.ObjectUtil;
import com.example.labelMark.domain.sysFile;
import com.example.labelMark.service.sysFileService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import com.example.labelMark.vo.constant.StatusEnum;
import io.swagger.annotations.ApiOperation;
import org.apache.commons.io.FileUtils;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.List;
import java.util.Map;


/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-04-18
 */
@RestController
@RequestMapping("/files")
public class sysFileController {

    @Resource
    private sysFileService sysfileService;

    private static final String TEMP_DIR = "com/example/labelMark/resource/temp";

    private static final String UPLOAD_DIR = "com/example/labelMark/resource/output";

    @PostMapping ("/uploadTif")
    public Result uploadTif(@RequestParam MultipartFile file)  {

        try {
            String[] fileNameArr = file.getOriginalFilename().split("\\.");
//            System.out.println(Arrays.toString(fileNameArr));
            String chunkDir = Paths.get(TEMP_DIR, fileNameArr[0]).toString();
            Files.createDirectories(Paths.get(chunkDir));

//            file.transferTo(Paths.get(chunkDir, fileNameArr[1]+"."+fileNameArr[2]).toFile());
            String fileName = fileNameArr[1]+"."+fileNameArr[2];
            File destFile = new File(chunkDir, fileName);
            file.transferTo(destFile);


        } catch (IOException | IllegalStateException e) {
            throw new RuntimeException(e);
        }

        return ResultGenerator.getSuccessResult();

    }

    /*    @PostMapping ("/mergeTif")
        public Result mergeTif(MultipartFile file){
            String[] fileNameArr = file.getOriginalFilename().split("\\.");
            String chunkDir = Paths.get(TEMP_DIR, fileNameArr[0]).toString();
            try {
                List<BufferedImage> images = loadImages(chunkDir);
                BufferedImage mergedImage = mergeImages(images);
    //            saveMergedImage(mergedImage, Paths.get(TEMP_DIR, "merged.jpg").toString());
                file.transferTo(Paths.get(UPLOAD_DIR, String.valueOf(mergedImage)).toFile());
            } catch (IOException e) {
                e.printStackTrace();
            }
            return ResultGenerator.getSuccessResult();
        }*/
    @PostMapping("/upload")
    public Result upload(@RequestParam("file") MultipartFile file,
                                         @RequestParam("fileName") String fileName,
                                         @RequestParam("chunkNumber") int chunkNumber,
                                         @RequestParam("totalChunks") int totalChunks) throws IOException {


        File uploadDirectory = new File(UPLOAD_DIR);
        if (!uploadDirectory.exists()) {
            uploadDirectory.mkdirs();
        }

        File destFile = new File(UPLOAD_DIR + File.separator + fileName + ".part" + chunkNumber);
        FileUtils.copyInputStreamToFile(file.getInputStream(), destFile);

        if (chunkNumber == totalChunks) { // 如果所有部分都已上传，则将它们组合成一个完整的文件
            String targetFilePath = UPLOAD_DIR + File.separator + fileName;
            for (int i = 1; i <= totalChunks; i++) {
                File partFile = new File(UPLOAD_DIR + File.separator + fileName + ".part" + i);
                try (FileOutputStream fos = new FileOutputStream(targetFilePath, true)) {
                    FileUtils.copyFile(partFile, fos);
                    partFile.delete();
                }
            }
        }

        return ResultGenerator.getSuccessResult("Upload successful");
    }


    @GetMapping("/getAllFiles")
    @ApiOperation("")
    public Map getAllFiles(Integer current,
                           Integer pageSize,
                           @RequestParam(required = false) Integer fileId) {
        try {
            //            无参时默认值
            if (ObjectUtil.isEmpty(current)) {
                current = 1;
            }
            if (ObjectUtil.isEmpty(pageSize)) {
                pageSize = 5;
            }
            List<sysFile> sysfiles = sysfileService.getAllFiles(current, pageSize, fileId);
            Map<String, Object> map = new HashMap<>();
            map.put("code", StatusEnum.SUCCESS);
            map.put("data", sysfiles);
            map.put("total", sysfiles.size());
            map.put("success", true);
            return map;
        } catch (Exception e) {
            Map<String, Object> map = new HashMap<>();
            map.put("code", StatusEnum.FAIL);
            map.put("success", false);
            map.put("message", e.getMessage());
            return map;
        }
    }


    @PutMapping("/updateFile")
    public Result updateFile(sysFile sysfile, String fileName){
        Integer fileId = sysfile.getFileId();
        sysfileService.updateFile(fileId, fileName);
        return ResultGenerator.getSuccessResult();
    }


    @DeleteMapping("/deleteFile")
    public Result deleteFile(String fileName){
        sysfileService.deleteFile(fileName);
        return ResultGenerator.getSuccessResult();
    }

    @GetMapping("getFilePath")
    public Result getFilePath(String fileName){
        String path = String.valueOf(Paths.get(UPLOAD_DIR, fileName));
        return ResultGenerator.getSuccessResult(path);
    }


//    public static List<BufferedImage> loadImages(String directoryPath) {
//        List<BufferedImage> images = new ArrayList<>();
//        try {
//            // 递归地访问目录，并筛选出所有.jpg文件
//            List<Path> imageFiles = Files.walk(Path.of(directoryPath), Integer.MAX_VALUE)
//                    .filter(path -> path.toString().toLowerCase().endsWith(".jpg"))
//                    .collect(Collectors.toList());
//
//            // 加载图片文件到BufferedImage对象的列表中
//            for (Path path : imageFiles) {
//                try {
//                    BufferedImage image = ImageIO.read(path.toFile());
//                    if (image != null) {
//                        images.add(image);
//                    }
//                } catch (IOException e) {
//                    // 错误处理，例如打印日志
//                    e.printStackTrace();
//                }
//            }
//        }  catch (IOException e) {
//            // 错误处理，例如打印日志
//            e.printStackTrace();
//        }
//        return images;
//    }
//
//    private static BufferedImage mergeImages(List<BufferedImage> images) throws IOException {
//        int width = images.stream().mapToInt(BufferedImage::getWidth).sum();
//        int height = images.get(0).getHeight();
//
//        BufferedImage mergedImage = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
//        Graphics2D g2d = mergedImage.createGraphics();
//
//        int x = 0;
//        for (BufferedImage image : images) {
//            g2d.drawImage(image, x, 0, null);
//            x += image.getWidth();
//        }
//
//        g2d.dispose();
//        return mergedImage;
//    }

//    private static void saveMergedImage(BufferedImage image, String outputPath) throws IOException {
//        ImageIO.write(image, "jpg", new sysFile(outputPath));
//    }

}
