package com.example.labelMark.service;

import com.example.labelMark.domain.Task;
import com.baomidou.mybatisplus.extension.service.IService;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Service
public interface TaskService extends IService<Task> {

    void createTask(Task task);

    List<Map<String, Object>> getTaskInfo();

    List<Integer> getIDs();

    void updateTaskById(int taskId, String taskName, String dataRange, String taskType, String mapServer);

    void deleteTaskById(int taskId);

    Task selectTaskById(int taskId);

    void updateTaskStatus(int taskId);

    void auditTask(int taskId, int status, String auditFeedback);

    List<Map<String, Object>> findAllTask();

    List<Map<String, Object>> findPublicTask();

    List<Map<String, Object>> findTasksByUsername(String username);

    List<String> findUserListByTaskId(int taskId);
}
