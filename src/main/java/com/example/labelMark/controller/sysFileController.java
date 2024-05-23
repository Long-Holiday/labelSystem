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
import java.util.*;


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


            File destFile = new File(chunkDir, String.valueOf(fileNameArr[1]));
            file.transferTo(destFile);


        } catch (IOException | IllegalStateException e) {
            throw new RuntimeException(e);
        }

        return ResultGenerator.getSuccessResult();

    }

    @PostMapping("/mergeTif")
    public Result mergeTif(@RequestParam String fileName, @RequestParam String updatetime, @RequestParam long size) {
        String[] fileNameArr = fileName.split("\\.");
        String chunkDir = Paths.get(TEMP_DIR, fileNameArr[0]).toString();
        String destFilePath = Paths.get(UPLOAD_DIR, fileName).toString();

        try {
            File dir = new File(chunkDir);
            File[] chunks = dir.listFiles();
            if (chunks != null) {
                Arrays.sort(chunks, Comparator.comparingInt(file -> Integer.parseInt(file.getName())));

                try (FileOutputStream out = new FileOutputStream(destFilePath)) {
                    for (File chunk : chunks) {
                        Files.copy(chunk.toPath(), out);
                    }
                }
            }

            // 删除临时切片目录
            Files.walk(Paths.get(chunkDir))
                    .sorted(Comparator.reverseOrder())
                    .map(java.nio.file.Path::toFile)
                    .forEach(File::delete);

            // 在数据库中创建文件记录
            sysfileService.createFile(fileName, updatetime, size);

        } catch (IOException e) {
            throw new RuntimeException(e);
        }

        return ResultGenerator.getSuccessResult("文件合并成功！");
    }
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


//    @PutMapping("/updateFile")
//    public Result updateFile(sysFile sysfile, String fileName){
//        Integer fileId = sysfile.getFileId();
//        sysfileService.updateFile(fileId, fileName);
//        return ResultGenerator.getSuccessResult();
//    }


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


//

}
