package com.example.labelMark.service.impl;

import com.example.labelMark.domain.Task;
import com.example.labelMark.mapper.TaskMapper;
import com.example.labelMark.service.TaskService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import io.swagger.models.auth.In;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Service
public class TaskServiceImpl extends ServiceImpl<TaskMapper, Task> implements TaskService {

    @Resource
    private TaskMapper taskMapper;
    @Override
    public void createTask(String dataRange, String taskName, String taskType, String mapServer) {
        Task task = new Task();
        task.setDateRange(dataRange);
        task.setTaskName(taskName);
        task.setTaskType(taskType);
        task.setMapServer(mapServer);
        taskMapper.insert(task);
    }

    @Override
    public List<Map<String, Object>> getTaskInfo() {
        List<Map<String, Object>> list = taskMapper.getTaskInfo();
        return list;
    }

    @Override
    public List<Integer> getIDs() {
        List<Integer> IDs = taskMapper.getIDs();
        return IDs;
    }

    @Override
    public void updateTaskById(int taskId, String taskName, String dataRange, String taskType, String mapServer) {

        taskMapper.updateTaskById(taskId, taskName, dataRange, taskType, mapServer);
    }

    @Override
    public void deleteTaskById(int taskId) {
        taskMapper.deleteById(taskId);
    }

    @Override
    public Task selectTaskById(int taskId) {
        Task task = taskMapper.selectTaskById(taskId);
        return task;
    }

    @Override
    public void updateTaskStatus(int taskId) {
        taskMapper.updateTaskStatus(taskId);
    }

    @Override
    public void auditTask(int taskId, int status, String auditFeedback) {
        taskMapper.auditTask(taskId, status, auditFeedback);
    }
}
