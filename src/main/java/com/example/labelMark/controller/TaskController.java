package com.example.labelMark.controller;

import cn.hutool.core.util.ObjectUtil;
import com.example.labelMark.domain.Mark;
import com.example.labelMark.domain.Task;
import com.example.labelMark.domain.TaskDatasetInfo;
import com.example.labelMark.domain.Type;
import com.example.labelMark.service.MarkService;
import com.example.labelMark.service.TaskAcceptedService;
import com.example.labelMark.service.TaskService;
import com.example.labelMark.service.TypeService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.TaskInfoDTO;
import com.example.labelMark.vo.constant.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import io.swagger.models.auth.In;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import javax.validation.constraints.Pattern;
import java.util.*;
import java.util.stream.Collectors;

import static com.example.labelMark.utils.CoordinateConverter.convertGeojson;

/**
 * <p>
 * 前端控制器
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@RestController
@RequestMapping("/task")
@Api(tags = "TASK业务控制器")
public class TaskController {

    @Resource
    private TaskService taskService;
    @Resource
    private TypeService typeService;

    @Resource
    private TaskAcceptedService taskAcceptedService;

    @Resource
    private MarkService markService;


    @PostMapping("/createTask")
    @ApiOperation("创建任务")
    public Result createTask(String dataRange, String taskName, String taskType, String mapServer) {
        int isSucceed = taskService.createTask(dataRange, taskName, taskType, mapServer);
        if (isSucceed != -1) {
            return ResultGenerator.getSuccessResult("插入成功");
        }
        return ResultGenerator.getSuccessResult("插入失败");
    }

    @PostMapping("/publishTask")
    @ApiOperation("创建任务,包括保存关联的指定任务用户和类型")
    public Result publishTask(@RequestBody Map<String, Object> map) {
        ArrayList<String> dateRange = (ArrayList<String>) map.get("daterange");
        String taskName = map.get("taskname").toString();
        String taskType = map.get("type").toString();
        ArrayList<String> usernameAndTypeArr = (ArrayList<String>) map.get("userArr");
        String mapServer = map.get("mapserver").toString();
        String dateRangeStr = dateRange.get(0) + " " + dateRange.get(1);
        int taskId = taskService.createTask(dateRangeStr, taskName, taskType, mapServer);
        if (taskId == -1) {
            return ResultGenerator.getSuccessResult("插入任务失败");
        }
//        拆解用户和所属类型
        String username, typeArr = "";
        for (String usernameAndType : usernameAndTypeArr) {
            String[] usernameAndTypeStr = usernameAndType.split(",");
            username = usernameAndTypeStr[0];
            for (int i = 1; i < usernameAndTypeStr.length; i++) {
                if (i == usernameAndTypeStr.length - 1) {
                    typeArr += usernameAndTypeStr[i];
                } else {
                    typeArr += usernameAndTypeStr[i] + ",";
                }
            }
            boolean taskAccept = taskAcceptedService.createTaskAccept(taskId, username, typeArr);
//            重置
            typeArr = "";
            if (taskAccept == false) {
                return ResultGenerator.getSuccessResult("插入接收任务失败");
            }
        }
        return ResultGenerator.getSuccessResult("插入成功");
    }

    @GetMapping("/getTaskInfo")
    @ApiOperation("获取任务")
    public Map<String, Object> getTaskInfo(@RequestParam(required = false) Integer taskid,
                                           @RequestParam(required = false) Integer current,
                                           @RequestParam(required = false) Integer pageSize,
                                           @RequestParam(required = false) String taskname,
                                           @RequestParam(required = false) String userArr,
                                           @RequestParam(required = false) Integer isAdmin) {

        //            无参时默认值
        if (ObjectUtil.isEmpty(current)) {
            current = 1;
        }
        if (ObjectUtil.isEmpty(pageSize)) {
            pageSize = 5;
        }
        int taskCount = taskService.getTotalTasks();
//非管理员只能看到自己的任务
        List<TaskInfoDTO> list = taskService.getTaskInfo(userArr);
        List<TaskInfoDTO> result = new ArrayList<>();
        for (TaskInfoDTO taskInfo : list) {
//            标记已经存在的同一任务taskInfo对象
            TaskInfoDTO existingObj = null;
            int index = -1;
            for (int i = 0; i < result.size(); i++) {
                if (ObjectUtil.equals(result.get(i).getTaskid(), taskInfo.getTaskid())) {
                    existingObj = result.get(i);
                    index = i;
                }
            }
//            处理typestring得到有效信息
            String typestring = taskInfo.getTypeArr();
            // 标注地图时才需要遍历标签方案
            List<Integer> type = new ArrayList<>();
            if (typestring != null && !typestring.isEmpty()) {
                type = Arrays.stream(typestring.split(","))
                        .map(Integer::parseInt)
                        .collect(Collectors.toList());
            }
            List<Type> typeArr = new ArrayList<>();
            if (ObjectUtil.isNotNull(taskInfo.getTaskid())) {
                for (Integer typeId : type) {
                    String typeName = typeService.getTypeNameById(typeId);
                    List<Type> types = typeService.getTypes(current, pageSize, typeId, typeName);
                    typeArr.add(types.get(0));
                }
            }
            Map<String, Object> info = new HashMap<>();
            info.put("userid", taskInfo.getUserid());
            info.put("username", taskInfo.getUsername());
            info.put("id", taskInfo.getId());
            info.put("typeArr", typeArr);
            if (existingObj != null) {
// 如果已经存在，直接将用户信息添加到 userArr 数组中
                List<Map<String, Object>> userArrOrigin = existingObj.getUserArr();
                userArrOrigin.add(info);
                taskInfo.setUserArr(userArrOrigin);
                result.set(index, taskInfo);
            } else {
                List<Map<String, Object>> userArrOrigin = new ArrayList<>();
                userArrOrigin.add(info);
                taskInfo.setUserArr(userArrOrigin);
                result.add(taskInfo);
            }
        }
        // 模糊查询：按任务名
        if (taskname != null && !taskname.isEmpty()) {
            result = result.stream()
                    .filter(item -> item.getTaskname().contains(taskname))
                    .collect(Collectors.toList());
        }
        // 模糊查询：按用户名，非管理员时执行
        if (userArr != null && !userArr.isEmpty() && isAdmin != null && isAdmin != 1) {
            result = result.stream()
                    .filter(item -> {
                        return item.getUserArr().stream()
                                .anyMatch(user -> user.equals(userArr));
                    })
                    .collect(Collectors.toList());
        }
        // 开始标注
        if (taskid != null) {
            result = result.stream()
                    .filter(item -> taskid.equals(item.getTaskid()))
                    .collect(Collectors.toList());
        }
        List<Mark> marks = markService.getMarkByTaskId(taskid);
        // 计算起始索引
        int startIndex = (current - 1) * pageSize;
        // 计算结束索引，这里需要做边界检查以避免越界
        int endIndex = Math.min(startIndex + pageSize, result.size());
//        模拟分页
        result = result.subList(startIndex, endIndex);
        Map<String, Object> responce = new HashMap<>();
        responce.put("code", 200);
        responce.put("data", result);
        responce.put("success", true);
        responce.put("markGeoJsonArr", convertGeojson(marks));
        responce.put("total", taskname != null || userArr != null ? result.size() : taskCount);
        return responce;
    }

    @PutMapping("/updateTask")
    public Result updateTask(@RequestBody Map<String, Object> map) {
        ArrayList<String> dateRange = (ArrayList<String>) map.get("daterange");
        String taskName = map.get("taskname").toString();
        String taskType = map.get("type").toString();
        ArrayList<String> usernameAndTypeArr = (ArrayList<String>) map.get("userArr");
        String mapServer = map.get("mapserver").toString();
        Integer taskId = Integer.valueOf(map.get("taskid").toString());
//        拼接起止日期
        String dateRangeStr = dateRange.get(0) + " " + dateRange.get(1);

        taskService.updateTaskById(taskId, taskName, dateRangeStr, taskType, mapServer);

        //        拆解用户和所属类型
        String username, typeArr = "";
        for (String usernameAndType : usernameAndTypeArr) {
            String[] usernameAndTypeStr = usernameAndType.split(",");
            username = usernameAndTypeStr[0];
            for (int i = 1; i < usernameAndTypeStr.length; i++) {
                if (i == usernameAndTypeStr.length - 1) {
                    typeArr += usernameAndTypeStr[i];
                } else {
                    typeArr += usernameAndTypeStr[i] + ",";
                }
            }
            boolean isUpdate = taskAcceptedService.createTaskAccept(taskId, username, typeArr);
//            重置
            typeArr = "";
            if (isUpdate == false) {
                return ResultGenerator.getSuccessResult("插入接收任务失败");
            }
        }
        return ResultGenerator.getSuccessResult("任务更新成功");
        }

    @DeleteMapping("/deleteTask/{taskId}")
    public Result deleteTask(@PathVariable int taskId) {
        taskAcceptedService.deleteTaskAcceptByTaskId(taskId);
        taskService.deleteTaskById(taskId);
        markService.deleteMarkByTaskId(taskId);
        return ResultGenerator.getSuccessResult("任务删除成功");
    }

    @PostMapping("/submitTask")
    public Result submitTask(@RequestBody Map<String, Object> map) {
        Integer taskId = (Integer) map.get("taskid");
        if (markService.GetTaskIdNum(taskId) == 0) {
            return ResultGenerator.getFailResult("未开始标注");
        }
        taskService.updateTaskStatus(taskId);
        return ResultGenerator.getSuccessResult("任务提交成功，审核中");
    }

    @PostMapping("/auditTask")
    public Result auditTask(@RequestBody Map<String, Object> map) {
        String audit_feedback = ObjectUtil.toString(map.get("auditfeedback"));
        Integer status = Integer.valueOf(ObjectUtil.toString(map.get("status")));
        Integer taskId = Integer.valueOf(ObjectUtil.toString(map.get("taskid")));
        taskService.auditTask(taskId, status, audit_feedback);
        return ResultGenerator.getSuccessResult("编辑任务完成，提交成功");
    }
}
