package com.example.labelMark.controller;

import cn.hutool.core.util.ObjectUtil;
import com.example.labelMark.domain.Mark;
import com.example.labelMark.domain.Type;
import com.example.labelMark.service.MarkService;
import com.example.labelMark.service.TaskService;
import com.example.labelMark.service.ModelService; // 新增导入
import com.example.labelMark.utils.CoordinateConverter;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import com.example.labelMark.vo.constant.StatusEnum;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.nio.file.Files;
import java.util.*;
import java.util.stream.Collectors;

// 导入 Jep 相关的类
//import jep.JepConfig;
//import jep.JepException;
//import jep.SharedInterpreter;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.nio.file.Paths;

import org.springframework.web.client.RestTemplate;

/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-04-28
 */
@RestController
@RequestMapping("/mark")
public class MarkController {

    @Resource
    private MarkService markService;

    @Resource
    private TaskService taskService;

    @Resource // 新增注入
    private ModelService modelService;

//    @PostMapping("/saveMarkInfo")
//    public Result saveMarkInfo(@RequestBody Map<String, Object> request) {
//        Integer userId = Integer.valueOf(request.get("userid").toString());
//        Integer taskId = Integer.valueOf(request.get("id").toString());
//        List<Map<String, Object>> typeIdAndMarkInfoArr = (List<Map<String, Object>>) request.get("jsondataArr");
//        List<Map<String, Object>> typeMapArr = (List<Map<String, Object>>) request.get("typeArr");
//        List<Type> typeArr = new ArrayList<>();
//        for (Map typeMap : typeMapArr) {
//            Type type = new Type();
//            Integer typeId = Integer.valueOf(typeMap.get("typeId").toString());
//            String typeName = typeMap.get("typeName").toString();
//            String typeColor = typeMap.get("typeColor").toString();
//            type.setTypeColor(typeColor);
//            type.setTypeName(typeName);
//            type.setTypeId(typeId);
//            typeArr.add(type);
//        }
//        List<Map<String, Object>> geometryArr = CoordinateConverter.convertCoordinate(typeIdAndMarkInfoArr);
//        List<Map<String, Object>> markInfoArr=geometryArr;
//        if (markInfoArr.isEmpty()) {
//            return ResultGenerator.getSuccessResult("没有标注信息，已删除多余Type");
//        }
////                筛选需要删除的标记
//        List<Mark> total = markService.getTotal();
//        for (Map<String, Object> geomAndTypeId : markInfoArr) {
//            Object markIdObj = geomAndTypeId.get("markId");
//            if (ObjectUtil.isNotNull(markIdObj)){
//                Integer markId = Integer.valueOf(markIdObj.toString());
////            排除了添加的标记(无markId)，还剩下需要修改，无变化（前两类都返回了markId）
////            和需要删除（不返回markId）的标记
//                Mark mark = markService.selectByMarkId(markId);
////                属于前两类,排除
//                if (ObjectUtil.isNotNull(mark)){
//                    total = total.stream()
//                            .filter(totalMarkItem -> totalMarkItem.getId() != markId)
//                            .collect(Collectors.toList());
//                }
//            }
//        }
////                删除需要删除的标记
//        markService.deleteMarks(total);
//        //此任务此用户是否已经标注
//        boolean exist = markService.isMark(taskId, userId);
//        if(exist) {
////            清空任务表中已存在的标注ID
//            taskService.updateTask(taskId, null);
//            updateTaskAndMark(userId, taskId, markInfoArr);
//            return ResultGenerator.getSuccessResult("已有有标注信息，已完成更新");
//        }else {
//            updateTaskAndMark(userId, taskId, markInfoArr);
//        }
//        return ResultGenerator.getSuccessResult("mark创建成功");
//    }
    @PostMapping("/saveMarkInfo")
    public Result saveMarkInfo(@RequestBody Map<String, Object> request) {
        Integer userId = Integer.valueOf(request.get("userid").toString());
        Integer taskId = Integer.valueOf(request.get("id").toString());
        List<Map<String, Object>> typeIdAndMarkInfoArr = (List<Map<String, Object>>) request.get("jsondataArr");
        List<Map<String, Object>> typeMapArr = (List<Map<String, Object>>) request.get("typeArr");
        List<Type> typeArr = new ArrayList<>();
        for (Map typeMap : typeMapArr) {
            Type type = new Type();
            Integer typeId = Integer.valueOf(typeMap.get("typeId").toString());
            String typeName = typeMap.get("typeName").toString();
            String typeColor = typeMap.get("typeColor").toString();
            type.setTypeColor(typeColor);
            type.setTypeName(typeName);
            type.setTypeId(typeId);
            typeArr.add(type);
        }
        List<Map<String, Object>> geometryArr = CoordinateConverter.convertCoordinate(typeIdAndMarkInfoArr);
        List<Map<String, Object>> markInfoArr=geometryArr;
        if (markInfoArr.isEmpty()) {
            return ResultGenerator.getSuccessResult("没有标注信息，已删除多余Type");
        }

        // **新增代码：删除当前用户和当前任务的所有旧标注信息**
        markService.deleteMarkByTaskAndUser(taskId, userId);

        //此任务此用户是否已经标注 (此处可以删除，因为上面已经删除了所有旧标记)
        boolean exist = markService.isMark(taskId, userId);
        if(exist) {
            //            清空任务表中已存在的标注ID (此处可以删除，因为上面已经删除了所有旧标记)
            taskService.updateTask(taskId, null);
            updateTaskAndMark(userId, taskId, markInfoArr);
            return ResultGenerator.getSuccessResult("已有有标注信息，已完成更新");
        }else {
            updateTaskAndMark(userId, taskId, markInfoArr);
        }
        return ResultGenerator.getSuccessResult("mark创建成功");
    }

    /**
     * 接收前端对标记的更改，更新或添加标记和任务信息
     * @param userId
     * @param taskId
     * @param markInfoArr
     */
    private void updateTaskAndMark(Integer userId, int taskId, List<Map<String, Object>> markInfoArr) {
        for (Map<String, Object> geomAndTypeId : markInfoArr) {
            Mark mark = new Mark();
            Integer markId = ObjectUtil.isNotNull(geomAndTypeId.get("markId"))
                    ?Integer.valueOf(geomAndTypeId.get("markId").toString()):null;
            mark.setId(markId);
            mark.setTaskId(taskId);
            mark.setUserId(userId);
            mark.setGeom(geomAndTypeId.get("geom").toString());
            mark.setStatus(0);
            mark.setTypeId(Integer.valueOf(geomAndTypeId.get("typeId").toString()));
            markService.insertOrUpdateMark(mark);
            //更新任务的标注ID
            String markIdStr = taskService.getMarkIdById(taskId);
            markIdStr = markIdStr == null ? mark.getId().toString()
                    : markIdStr + "," + mark.getId().toString();
            taskService.updateTask(taskId, markIdStr);
        }
    }
//    尝试使用JEP效果不好
//    @PostMapping("/assistFunction")
//    public Result callPythonScript(@RequestBody Map<String, Object> request) {
//        Integer taskId = Integer.valueOf(request.get("taskid").toString());
//
//        try (SharedInterpreter interp = new SharedInterpreter()) {
//            // 1. 设置 Python 脚本所在的目录（如果脚本不在当前工作目录）
//            interp.exec("import sys");
//            interp.exec("sys.path.append('/home/change/labelcode/labelMark/python_scripts')");  // 替换为你的 Python 脚本所在目录
//
//            // 2. 导入 Python 模块
//            interp.exec("from test import Test"); // 假设你的脚本名为 test.py, 且有一个 classify 函数
//
//            // 3. 设置参数（如果需要）
//            // interp.set("image_path", "test_image.jpg"); //  如果需要传递其他参数
//            interp.set("task_id", taskId); // 将 taskId 传递给 Python
//
//            // 4. 调用 Python 函数
//            interp.exec("result = Test(task_id)");
//
//            // 5. 获取返回值（如果需要）
//              int Index = interp.getValue("result", Integer.class); // 如果 classify 函数有返回值
//              System.out.println("结果: " + Index);
//
//            // 注意：这里我们假设 classify 函数只是打印 task_id，没有返回值。
//            //      如果有返回值，你需要根据返回值的类型使用 interp.getValue() 获取。
//
//        } catch (JepException e) {
//            e.printStackTrace();
//            return ResultGenerator.getFailResult("调用 Python 脚本失败: " + e.getMessage());
//        }
//
//        return ResultGenerator.getSuccessResult("成功调用 Python 脚本");
//    }

    //响应前端辅助功能
    @PostMapping("/assistFunction")
    public Map<String, Object> assistFunction(@RequestBody Map<String, Object> request) {
        // 获取前端传来的参数
        String taskId = request.get("taskid").toString();
        String functionName = request.get("functionName").toString();
        String assistInput = request.get("assistInput") != null ? request.get("assistInput").toString() : "";
        String userId = request.get("user_id") != null ? request.get("user_id").toString() : null;
        String modelName = request.get("modelName") != null ? request.get("modelName").toString() : null;
        @SuppressWarnings("unchecked")
        Map<String, Object> params = (Map<String, Object>) request.get("parameters");
        // 任务类型
        String tasktype = request.get("task_type") != null ? request.get("task_type").toString() : "";

        // 获取四个参数，处理可能的 null 值
        String param1 = params.get("param1") != null ? params.get("param1").toString() : "";
        String param2 = params.get("param2") != null ? params.get("param2").toString() : "";
        String param3 = params.get("param3") != null ? params.get("param3").toString() : "";
        String param4 = params.get("param4") != null ? params.get("param4").toString() : "";

        // 获取 modelScope 数据
        String modelScopeStr = "";
        if (params.containsKey("modelScope") && params.get("modelScope") != null) {
            Object modelScope = params.get("modelScope");
            // 将 modelScope 转换为 JSON 字符串
            ObjectMapper objectMapper = new ObjectMapper();
            try {
                modelScopeStr = objectMapper.writeValueAsString(modelScope);
            } catch (JsonProcessingException e) {
                e.printStackTrace();
                Map<String, Object> response = new HashMap<>();
                response.put("code", StatusEnum.FAIL.code);
                response.put("message", "解析模型作用范围失败: " + e.getMessage());
                return response;
            }
        } else {
            modelScopeStr = ""; // 如果没有 modelScope，传递空数组
        }

        // 设置文件路径
        Path mapfile_path = Paths.get(System.getProperty("user.dir") + File.separator +
                "src/main/java/com/example/labelMark/resource/output");

        // 准备请求体
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("taskid", taskId);
        requestBody.put("mapfile_path", mapfile_path.toString());
        requestBody.put("functionName", functionName);
        requestBody.put("assistInput", assistInput);
        requestBody.put("modelName", modelName);
        requestBody.put("param1", param1);
        requestBody.put("param2", param2);
        requestBody.put("param3", param3);
        requestBody.put("param4", param4);
        requestBody.put("user_id", userId);
        requestBody.put("modelScopeStr", modelScopeStr);
        requestBody.put("tasktype", tasktype);

        System.out.println(requestBody);

        // 发送 POST 请求到 FastAPI
        RestTemplate restTemplate = new RestTemplate();
        String url = "http://localhost:5000/assistFunction"; // FastAPI 服务地址
        Map<String, Object> response = restTemplate.postForObject(url, requestBody, Map.class);

        return response;
    }
//    @PostMapping("/assistFunction")
//    public Map<String, Object> PythonScript_assistFunction(@RequestBody Map<String, Object> request) {
//        // 获取前端传来的参数
//        String taskId = request.get("taskid").toString();
//        //模型名称
//        String functionName = request.get("functionName").toString();
//        //训练次数
//        String assistInput = request.get("assistInput") != null ? request.get("assistInput").toString() : "";
//        // userid
//        String userId = request.get("user_id") != null ? request.get("user_id").toString() : null;
//
//        // 获取 parameters 对象
//        @SuppressWarnings("unchecked")
//        Map<String, Object> params = (Map<String, Object>) request.get("parameters");
//
//        // 获取四个参数，处理可能的 null 值
//        String param1 = params.get("param1") != null ? params.get("param1").toString() : "";
//        String param2 = params.get("param2") != null ? params.get("param2").toString() : "";
//        String param3 = params.get("param3") != null ? params.get("param3").toString() : "";
//        String param4 = params.get("param4") != null ? params.get("param4").toString() : "";
//
//        // 获取 modelScope 数据
//        String modelScopeStr = "";
//        if (params.containsKey("modelScope") && params.get("modelScope") != null) {
//            Object modelScope = params.get("modelScope");
//            // 将 modelScope 转换为 JSON 字符串
//            ObjectMapper objectMapper = new ObjectMapper();
//            try {
//                modelScopeStr = objectMapper.writeValueAsString(modelScope);
//            } catch (JsonProcessingException e) {
//                e.printStackTrace();
//                Map<String, Object> response = new HashMap<>();
//                response.put("code", StatusEnum.FAIL.code);
//                response.put("message", "解析模型作用范围失败: " + e.getMessage());
//                return response;
//            }
//        } else {
//            modelScopeStr = "[]"; // 如果没有 modelScope，传递空数组
//        }
//
//        // 设置文件路径
//        Path mapfile_path = Paths.get(System.getProperty("user.dir") + File.separator +
//                "src/main/java/com/example/labelMark/resource/output");
//        Path python_path = Paths.get(System.getProperty("user.dir") + File.separator +
//                "src/main/java/com/example/labelMark/python_scripts/main.py");
//
//        try {
//            // 创建 ProcessBuilder，指定 Python 解释器和脚本路径
//            ProcessBuilder pb = new ProcessBuilder("/home/change/anaconda3/envs/label/bin/python",
//                    python_path.toString());
//
//            // 添加所有参数到命令行
//            pb.command().add(taskId);          // taskId
//            pb.command().add(mapfile_path.toString());  // mapfile_path
//            pb.command().add(functionName);    // functionName
//            pb.command().add(assistInput);     // assistInput
//            pb.command().add(param1);          // param1
//            pb.command().add(param2);          // param2
//            pb.command().add(param3);          // param3
//            pb.command().add(param4);          // param4
//            pb.command().add(userId);
//            pb.command().add(modelScopeStr);
//            System.out.println("Command: " + pb.command());
//
//            // 启动进程
//            Process process = pb.start();
//            long pid = process.pid();
//            System.out.println("Python PID: " + pid);
//
//            // 读取标准输出
//            BufferedReader stdInput = new BufferedReader(new InputStreamReader(process.getInputStream()));
//            // 读取错误输出
//            BufferedReader stdError = new BufferedReader(new InputStreamReader(process.getErrorStream()));
//
//            String s;
//            StringBuilder output = new StringBuilder();
//            while ((s = stdInput.readLine()) != null) {
//                output.append(s).append("\n");
//            }
//
//            StringBuilder errorOutput = new StringBuilder();
//            while ((s = stdError.readLine()) != null) {
//                errorOutput.append(s).append("\n");
//            }
//
//            // 等待进程完成
//            int exitCode = process.waitFor();
//
//            // 创建响应 Map
//            Map<String, Object> response = new HashMap<>();
//
//            if (exitCode == 0) {
//                // 成功
//                System.out.println("Python 脚本输出: " + output);
//                response.put("code", StatusEnum.SUCCESS.code);
//                response.put("message", "成功调用辅助功能");
//                return response;
//            } else {
//                // 失败
//                System.err.println("Python 脚本错误输出: " + errorOutput);
//                response.put("code", StatusEnum.FAIL.code);
//                response.put("message", "调用辅助功能失败: " + errorOutput.toString());
//                return response;
//            }
//
//        } catch (IOException | InterruptedException e) {
//            e.printStackTrace();
//            Map<String, Object> response = new HashMap<>();
//            response.put("code", StatusEnum.FAIL.code);
//            response.put("message", "调用辅助功能失败: " + e.getMessage());
//            return response;
//        }
//    }
    //响应前端模型推理功能
    @PostMapping("/inferenceFunction")
    public Map<String, Object> PythonScript_inferenceFunction(@RequestBody Map<String, Object> request) {
        // 获取前端传来的参数
        String taskId = request.get("taskid").toString();
        // user_id
        String userId = request.get("user_id").toString();
        // 模型名称
        String model_name = request.get("model") != null ? request.get("model").toString() : "";


        // 获取 parameters 对象
        @SuppressWarnings("unchecked")
        Map<String, Object> params = (Map<String, Object>) request.get("parameters");

        // 获取四个参数，处理可能的 null 值
        String param1 = params.get("param1") != null ? params.get("param1").toString() : "";
        String param2 = params.get("param2") != null ? params.get("param2").toString() : "";
        String param3 = params.get("param3") != null ? params.get("param3").toString() : "";
        String param4 = params.get("param4") != null ? params.get("param4").toString() : "";
        String param5 = params.get("param5") != null ? params.get("param5").toString() : "";
        String param6 = params.get("param6") != null ? params.get("param6").toString() : "";
        String param7 = params.get("param7") != null ? params.get("param7").toString() : "";
        String param8 = params.get("param8") != null ? params.get("param8").toString() : "";


        // 获取 modelScope 数据
        String modelScopeStr = "";
        if (params.containsKey("modelScope") && params.get("modelScope") != null) {
            Object modelScope = params.get("modelScope");
            // 将 modelScope 转换为 JSON 字符串
            ObjectMapper objectMapper = new ObjectMapper();
            try {
                modelScopeStr = objectMapper.writeValueAsString(modelScope);
            } catch (JsonProcessingException e) {
                e.printStackTrace();
                Map<String, Object> response = new HashMap<>();
                response.put("code", StatusEnum.FAIL.code);
                response.put("message", "解析模型作用范围失败: " + e.getMessage());
                return response;
            }
        } else {
            modelScopeStr = "[]"; // 如果没有 modelScope，传递空数组
        }

        // 设置文件路径
        Path mapfile_path = Paths.get(System.getProperty("user.dir") + File.separator +
                "src/main/java/com/example/labelMark/resource/output");
//        Path python_path = Paths.get(System.getProperty("user.dir") + File.separator +
//                "src/main/java/com/example/labelMark/python_scripts/inference.py");

        // 准备请求体
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("taskid", taskId);
        requestBody.put("mapfile_path", mapfile_path.toString());
        requestBody.put("user_id", userId);
        requestBody.put("model", model_name);
        requestBody.put("param1", param1);
        requestBody.put("param2", param2);
        requestBody.put("param3", param3);
        requestBody.put("param4", param4);
        requestBody.put("param5", param5);
        requestBody.put("param6", param6);
        requestBody.put("param7", param7);
        requestBody.put("param8", param8);
        requestBody.put("modelScopeStr", modelScopeStr);

        // 发送 POST 请求到 FastAPI
        RestTemplate restTemplate = new RestTemplate();
        String url = "http://localhost:5000/inferenceFunction"; // FastAPI 服务地址
        Map<String, Object> response = restTemplate.postForObject(url, requestBody, Map.class);

        return response;

//        try {
//            // 创建 ProcessBuilder，指定 Python 解释器和脚本路径
//            ProcessBuilder pb = new ProcessBuilder("/home/change/anaconda3/envs/label/bin/python",
//                    python_path.toString());
//
//            // 添加所有参数到命令行
//            pb.command().add(taskId);          // taskId
//            pb.command().add(mapfile_path.toString());  // mapfile_path
//            pb.command().add(userId);    // userid
//            pb.command().add(model_name);     // model_name
//            pb.command().add(param1);          // param1
//            pb.command().add(param2);          // param2
//            pb.command().add(param3);          // param3
//            pb.command().add(param4);          // param4
//            pb.command().add(modelScopeStr);
//            System.out.println("Command: " + pb.command());
//
//            // 启动进程
//            Process process = pb.start();
//
//            // 读取标准输出
//            BufferedReader stdInput = new BufferedReader(new InputStreamReader(process.getInputStream()));
//            // 读取错误输出
//            BufferedReader stdError = new BufferedReader(new InputStreamReader(process.getErrorStream()));
//
//            String s;
//            StringBuilder output = new StringBuilder();
//            while ((s = stdInput.readLine()) != null) {
//                output.append(s).append("\n");
//            }
//
//            StringBuilder errorOutput = new StringBuilder();
//            while ((s = stdError.readLine()) != null) {
//                errorOutput.append(s).append("\n");
//            }
//
//            // 等待进程完成
//            int exitCode = process.waitFor();
//
//            // 创建响应 Map
//            Map<String, Object> response = new HashMap<>();
//
//            if (exitCode == 0) {
//                // 成功
//                System.out.println("Python 脚本输出: " + output);
//                response.put("code", StatusEnum.SUCCESS.code);
//                response.put("message", "模型推理成功");
//                return response;
//            } else {
//                // 失败
//                System.err.println("Python 脚本错误输出: " + errorOutput);
//                response.put("code", StatusEnum.FAIL.code);
//                response.put("message", "模型推理失败: " + errorOutput.toString());
//                return response;
//            }
//
//        } catch (IOException | InterruptedException e) {
//            e.printStackTrace();
//            Map<String, Object> response = new HashMap<>();
//            response.put("code", StatusEnum.FAIL.code);
//            response.put("message", "模型推理失败: " + e.getMessage());
//            return response;
//        }
    }

    @PostMapping("/getModelList")
    public Map<String, Object> getModelList(@RequestBody Map<String, String> request) {
        // 获取前端传来的用户ID
        String userIdStr = request.get("user_id");
        System.out.println("当前userid为" + userIdStr);

        String taskType = request.get("task_type");

        Map<String, Object> response = new HashMap<>();

        if (userIdStr == null || userIdStr.trim().isEmpty()) {
            response.put("code", StatusEnum.FAIL.code);
            response.put("message", "用户ID不能为空");
            return response;
        }

        try {
            Integer userId = Integer.valueOf(userIdStr);
            // 调用 ModelService 获取模型数据 Map
            Map<String, String> modelMap = modelService.getModelMapByUserId(userId, taskType);

            if (modelMap.isEmpty()) {
                response.put("code", StatusEnum.SUCCESS.code);
                response.put("message", "该用户没有关联的模型");
                response.put("data", new HashMap<>()); // 返回空 Map
            } else {
                response.put("code", StatusEnum.SUCCESS.code);
                response.put("message", "成功获取模型列表");
                response.put("data", modelMap);
            }

            System.out.println("Model List for user " + userId + ": " + modelMap);
            return response;

        } catch (NumberFormatException e) {
            response.put("code", StatusEnum.FAIL.code);
            response.put("message", "无效的用户ID格式");
            return response;
        } catch (Exception e) {
            e.printStackTrace();
            response.put("code", StatusEnum.FAIL.code);
            response.put("message", "获取模型列表失败: " + e.getMessage());
            return response;
        }
    }

    //响应前端样本更新
    @PostMapping("/update_label")
    public Map<String, Object> PythonScript_updatelabel(@RequestBody Map<String, Object> request) { // 返回 Map
        //得到前端传回的taskid，并且设置python文件以及tif影像所在位置
        Integer taskId = Integer.valueOf(request.get("taskid").toString());
        Path mapfile_path = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/resource/output");
//        Path python_path = Paths.get(System.getProperty("user.dir")+ File.separator + "src/main/java/com/example/labelMark/python_scripts/update_label.py");

        // 准备请求体
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("taskid", taskId.toString());
        requestBody.put("mapfile_path", mapfile_path.toString());

        // 发送 POST 请求到 FastAPI
        RestTemplate restTemplate = new RestTemplate();
        String url = "http://localhost:5000/update_label"; // FastAPI 服务地址
        Map<String, Object> response = restTemplate.postForObject(url, requestBody, Map.class);

        return response;
//        try {
//            //将"/home/change/anaconda3/envs/label_env/bin/python"换成你python解释器的路径位置
//            ProcessBuilder pb = new ProcessBuilder("/home/change/anaconda3/envs/label/bin/python", python_path.toString());
//            //设置需要传个python的变量
//            pb.command().add(taskId.toString());
//            pb.command().add(mapfile_path.toString());
//            Process process = pb.start();
//
//            BufferedReader stdInput = new BufferedReader(new InputStreamReader(process.getInputStream()));
//            BufferedReader stdError = new BufferedReader(new InputStreamReader(process.getErrorStream()));
//
//            String s;
//            StringBuilder output = new StringBuilder();
//            while ((s = stdInput.readLine()) != null) {
//                output.append(s).append("\n");
//            }
//
//            StringBuilder errorOutput = new StringBuilder();
//            while ((s = stdError.readLine()) != null) {
//                errorOutput.append(s).append("\n");
//            }
//
//            int exitCode = process.waitFor();
//
//            if (exitCode == 0) {
//                // 成功
//                System.out.println("Python 脚本输出: " + output);
//
//                // 直接返回 Map，不包含 data
//                Map<String, Object> response = new HashMap<>();
//                response.put("code", StatusEnum.SUCCESS.code);
//                response.put("message", "成功更新样本");
//                return response;
//
//
//            } else {
//                // 失败
//                System.err.println("Python 脚本错误输出: " + errorOutput);
//                Map<String, Object> response = new HashMap<>();
//                response.put("code", StatusEnum.FAIL.code);
//                response.put("message", "更新样本失败: " + errorOutput);
//                return response;
//            }
//
//        } catch (IOException | InterruptedException e) {
//            e.printStackTrace();
//            Map<String, Object> response = new HashMap<>();
//            response.put("code", StatusEnum.FAIL.code);
//            response.put("message", "更新样本失败: " + e.getMessage());
//            return response;
//        }
    }

}
