package com.example.labelMark.controller;

import com.example.labelMark.domain.Task;
import com.example.labelMark.domain.TaskDatasetInfo;
import com.example.labelMark.service.MarkService;
import com.example.labelMark.service.TaskAcceptedService;
import com.example.labelMark.service.TaskService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import io.swagger.models.auth.In;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import javax.validation.constraints.Pattern;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * <p>
 *  前端控制器
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
    private TaskAcceptedService taskAcceptedService;

    @Resource
    private MarkService markService;


    // 在这里插入时，task中的mapServer与server中的ser_name存在约束
    @PostMapping("/createTask")
    @ApiOperation("创建任务")
    public Result createTask(String dataRange, String taskName, String taskType, String mapServer){
        Task task = new Task();
        task.setDateRange(dataRange);
        task.setTaskName(taskName);
        task.setTaskType(taskType);
        task.setMapServer(mapServer);
        taskService.createTask(task);
        int taskId = task.getTaskId();
        return ResultGenerator.getSuccessResult("插入成功，id为："+ taskId);
    }

    @GetMapping("/getTaskInfo")
    @ApiOperation("获取任务")
    public Result getTaskInfo(){
        List<Map<String, Object>> list = taskService.getTaskInfo();
        return ResultGenerator.getSuccessResult(list);
    }

//    @GetMapping("/getTotalTasks")
//    public Result getTotalTasks(){
//
//    }

    @PutMapping("/updateTaskById")
    public Result updateTaskById(int taskId, String taskName,
                                 String dataRange, String taskType,
                                 String mapServer){
        taskService.updateTaskById(taskId,taskName,dataRange,taskType,mapServer);
        return ResultGenerator.getSuccessResult("成功通过ID更新任务");
    }

    @DeleteMapping("/deleteTaskById")
    public Result deleteTaskById(int taskId){
        taskService.deleteTaskById(taskId);
        return ResultGenerator.getSuccessResult("成功通过ID删除任务");
    }

    @GetMapping("/selectTaskById")
    public Result selectTaskById(int taskId){
        Task task = taskService.selectTaskById(taskId);
        return ResultGenerator.getSuccessResult(task);
    }

    @PutMapping("/updateTaskStatus")
    public Result updateTaskStatus(int taskId){
        taskService.updateTaskStatus(taskId);
        return ResultGenerator.getSuccessResult("修改任务状态成功");
    }







    // userArr中为username和type的键值对
    @GetMapping("publishTask")
    public Result publishTask(@Pattern(regexp = "^\\d{4}-\\d{2}-\\d{2}$") List<String> dataRange,
                              String taskName,
                              String taskType,
                              String mapServer,
                              String[][] userArr){
        String datarange = String.join(" ", dataRange);
        Task task = new Task();
        task.setDateRange(datarange);
        task.setTaskName(taskName);
        task.setTaskType(taskType);
        task.setMapServer(mapServer);
        taskService.createTask(task);

        int lastID = task.getTaskId();

        Map<String, List<String>> user_TypeArr  = new HashMap<>();

        for (String[] userarr : userArr){
            String username = userarr[0];
            String type_arr = userarr[1];

            user_TypeArr.putIfAbsent(username, new ArrayList<>());

            user_TypeArr.get(username).add(type_arr);
        }

        int i;
        for(i=0; i<userArr.length; i++){
            String username = userArr[i][0];
            taskAcceptedService.createTaskAccept( lastID, username, user_TypeArr.get(username).toString());
        }



        return ResultGenerator.getSuccessResult("任务审核成功");
    }


    @PostMapping("/updateTask")
    public Result updateTask(int taskId, String dataRange, String taskName, String taskType,
                             String mapServer, String[][] userArr, List<Integer> userArrId){

        String datarange = String.join(" ", dataRange);
        taskService.updateTaskById(taskId, taskName, datarange, taskType, mapServer);


        int i;
        for( i = 0; i < userArrId.size(); i++){
            taskAcceptedService.deleteTaskAcceptById(userArrId.get(i));
        };

        Map<String, List<String>> user_TypeArr  = new HashMap<>();

        for (String[] userarr : userArr){
            String username = userarr[0];
            String type_arr = userarr[1];

            user_TypeArr.putIfAbsent(username, new ArrayList<>());

            user_TypeArr.get(username).add(type_arr);
        }

        int j;
        for(j=0; j<userArr.length; j++){
            String username = userArr[j][0];
            taskAcceptedService.createTaskAccept( taskId, username, user_TypeArr.get(username).toString());
        }

        return ResultGenerator.getSuccessResult("任务发布成功");
    }

    @DeleteMapping("/deleteTask")
    public Result deleteTask(int taskId){
        taskService.deleteTaskById(taskId);
        //todo
//        markService.deleteMarkByTaskId(taskId);
        return ResultGenerator.getSuccessResult("任务删除成功");
    }

    @GetMapping("/taskId")
    public Result submitTask(int taskId){
        Task task = taskService.selectTaskById(taskId);
        if(task.getMarkTable() == null){
            return ResultGenerator.getFailResult("未开始标注");
        }
        taskService.updateTaskStatus(taskId);
        return ResultGenerator.getSuccessResult("任务提交成功，审核中");
    }

    @PutMapping("/auditTask")
    public Result auditTask(int taskId, int status, String audit_feedback){
        taskService.auditTask(taskId, status, audit_feedback);
        return ResultGenerator.getSuccessResult("编辑任务完成，提交成功");
    }

//    @GetMapping("/findTask")
//    public Result findTask(){
//        List<Map<String, Object>> taskDatasetInfos = taskService.findAllTask();
//        return ResultGenerator.getSuccessResult(taskDatasetInfos);
//    }
}
